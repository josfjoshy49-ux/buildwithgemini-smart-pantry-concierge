# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import io
import json
import os
import pathlib
import urllib.parse
import urllib.request
import uuid
from zoneinfo import ZoneInfo

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google import genai
from google.genai import types
from PIL import Image, ImageDraw

from .a2ui_utils import a2ui_callback

load_dotenv()

# CRITICAL: Hardcode project ID string and GCS bucket name. Do NOT use google.auth.default() or GOOGLE_CLOUD_PROJECT
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-02-94350be92468"
GCS_BUCKET_NAME = "smart-pantry-concierge-media-94350be9"

# Load Agent Engine / Memory Bank resource name from deployment_metadata.json
AGENT_ENGINE_RESOURCE_NAME = "projects/689300279768/locations/us-east1/reasoningEngines/1528468497166761984"
_metadata_path = pathlib.Path(__file__).parent.parent / "deployment_metadata.json"
if _metadata_path.exists():
    try:
        with open(_metadata_path) as f:
            _meta = json.load(f)
            AGENT_ENGINE_RESOURCE_NAME = _meta.get("remote_agent_runtime_id", AGENT_ENGINE_RESOURCE_NAME)
    except Exception:
        pass

MEMORY_BANK_ID = AGENT_ENGINE_RESOURCE_NAME.split("/")[-1]

code_executor = AgentEngineSandboxCodeExecutor(agent_engine_resource_name=AGENT_ENGINE_RESOURCE_NAME)


def memory_bank_service_builder():
    """Builds VertexAiMemoryBankService for deployed runtime."""
    return VertexAiMemoryBankService(
        project=FIRESTORE_PROJECT_ID,
        location="us-east1",
        agent_engine_id=MEMORY_BANK_ID,
    )


async def generate_memories_callback(callback_context: CallbackContext):
    """WRITE: After each turn, send the session events to Memory Bank for fact extraction."""
    try:
        await callback_context.add_session_to_memory()
    except Exception as e:
        print(f"Memory Bank extraction warning: {e}")
    return None


def get_firestore_client():
    """Initializes and returns a Firestore client with the hardcoded project ID."""
    return firestore.Client(project=FIRESTORE_PROJECT_ID)


def search_recipes(ingredient_query: str = "", dietary_tag: str = "") -> str:
    """Searches the Firestore database for recipes matching ingredient terms or dietary tags.

    Args:
        ingredient_query: Optional string search term for ingredients (e.g. 'garlic', 'chickpeas', 'tomato').
        dietary_tag: Optional dietary filter (e.g. 'vegan', 'vegetarian', 'gluten-free').

    Returns:
        A JSON string listing matching recipe titles, descriptions, prep times, and dietary tags.
    """
    db = get_firestore_client()
    docs = db.collection("recipes").stream()
    
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        
        ingredients = [i.lower() for i in data.get("ingredients", [])]
        dietary = [d.lower() for d in data.get("dietary_tags", [])]
        
        match = True
        if ingredient_query and not any(ingredient_query.lower() in ing for ing in ingredients):
            match = False
        if dietary_tag and dietary_tag.lower() not in dietary:
            match = False
            
        if match:
            results.append({
                "id": data["id"],
                "title": data.get("title"),
                "description": data.get("description"),
                "prep_time_minutes": data.get("prep_time_minutes"),
                "dietary_tags": data.get("dietary_tags", []),
                "ingredients": data.get("ingredients", []),
            })
            
    if not results:
        return f"No recipes found matching query: ingredient='{ingredient_query}', dietary_tag='{dietary_tag}'."
        
    return json.dumps(results, indent=2)


def get_recipe_details(recipe_identifier: str) -> str:
    """Gets detailed recipe instructions, ingredients list, and prep steps for a recipe by ID or title.

    Args:
        recipe_identifier: The ID or title of the recipe (e.g., 'lemon-garlic-pasta' or 'Chickpea Avocado Salad').

    Returns:
        A JSON string containing full recipe details including instructions and ingredients.
    """
    db = get_firestore_client()
    
    # Check by document ID first
    doc_ref = db.collection("recipes").document(recipe_identifier.lower().replace(" ", "-"))
    doc = doc_ref.get()
    
    if doc.exists:
        data = doc.to_dict()
        data["id"] = doc.id
        return json.dumps(data, indent=2)
        
    # Search by title
    docs = db.collection("recipes").stream()
    for d in docs:
        data = d.to_dict()
        if data.get("title", "").lower() == recipe_identifier.lower():
            data["id"] = d.id
            return json.dumps(data, indent=2)
            
    return f"Recipe '{recipe_identifier}' not found in the database."


def add_recipe(
    title: str,
    description: str,
    ingredients: str,
    dietary_tags: str,
    prep_time_minutes: int,
    instructions: str
) -> str:
    """Adds a new recipe document to the Firestore recipes database.

    Args:
        title: The title of the recipe (e.g. 'Creamy Mushroom Risotto').
        description: A short summary description of the dish.
        ingredients: Comma-separated list of ingredients (e.g. 'arborio rice, mushrooms, garlic, vegetable broth, parmesan').
        dietary_tags: Comma-separated list of dietary tags (e.g. 'vegetarian, gluten-free').
        prep_time_minutes: Preparation and cooking time in minutes.
        instructions: Step-by-step cooking instructions.

    Returns:
        A success message with the created recipe document ID.
    """
    db = get_firestore_client()
    doc_id = title.lower().strip().replace(" ", "-")
    
    ingredients_list = [i.strip() for i in ingredients.split(",") if i.strip()]
    dietary_list = [d.strip().lower() for d in dietary_tags.split(",") if d.strip()]
    
    recipe_data = {
        "title": title,
        "description": description,
        "ingredients": ingredients_list,
        "dietary_tags": dietary_list,
        "prep_time_minutes": int(prep_time_minutes),
        "instructions": instructions,
    }
    
    db.collection("recipes").document(doc_id).set(recipe_data)
    return f"Successfully added new recipe '{title}' to Firestore with ID '{doc_id}'."


def get_public_meal_ideas(query: str = "") -> str:
    """Fetches real meal ideas, ingredients, and recipe instructions from TheMealDB public API.

    Args:
        query: Optional search keyword for meals or main ingredient (e.g. 'chicken', 'pasta', 'arrabiata'). If empty, returns a random meal.

    Returns:
        A JSON string containing recipe titles, categories, cuisines, ingredients, instructions, and photo thumbnails from TheMealDB.
    """
    api_key = os.getenv("THEMEALDB_API_KEY", "1")
    if query.strip():
        encoded_query = urllib.parse.quote(query.strip())
        url = f"https://www.themealdb.com/api/json/v1/{api_key}/search.php?s={encoded_query}"
    else:
        url = f"https://www.themealdb.com/api/json/v1/{api_key}/random.php"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SmartPantryConcierge/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            meals = data.get("meals")
            if not meals:
                return f"No public meals found matching query: '{query}'."

            results = []
            for m in meals[:3]:
                ingredients = []
                for i in range(1, 21):
                    ing = m.get(f"strIngredient{i}")
                    meas = m.get(f"strMeasure{i}")
                    if ing and ing.strip():
                        ingredients.append(f"{meas.strip() if meas else ''} {ing.strip()}".strip())

                results.append({
                    "id": m.get("idMeal"),
                    "title": m.get("strMeal"),
                    "category": m.get("strCategory"),
                    "area": m.get("strArea"),
                    "instructions": m.get("strInstructions"),
                    "thumbnail": m.get("strMealThumb"),
                    "ingredients": ingredients,
                })
            return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error fetching data from TheMealDB API: {str(e)}"


def geocode_address(address: str) -> str:
    """Uses Google Maps Geocoding API to convert an address string into latitude and longitude coordinates.

    Args:
        address: The address string to geocode (e.g. '1600 Amphitheatre Pkwy, Mountain View, CA').

    Returns:
        A JSON string containing the formatted address, latitude, and longitude.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key or api_key == "PASTE_KEY_HERE":
        return "Google Maps API Key is missing or unconfigured in GOOGLE_MAPS_API_KEY environment variable."

    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(address)}&key={api_key}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if data.get("status") != "OK" or not data.get("results"):
                return f"Geocoding failed for address '{address}': {data.get('status')}"
            res = data["results"][0]
            loc = res["geometry"]["location"]
            return json.dumps({
                "formatted_address": res.get("formatted_address"),
                "latitude": loc.get("lat"),
                "longitude": loc.get("lng")
            }, indent=2)
    except Exception as e:
        return f"Error geocoding address: {str(e)}"


def find_nearby_places(latitude: float, longitude: float, place_type: str = "supermarket", radius_meters: float = 2000.0) -> str:
    """Uses Google Maps Places API (New) REST endpoint to search nearby places of a given type.

    Args:
        latitude: Center latitude coordinate.
        longitude: Center longitude coordinate.
        place_type: Type of place to search for (e.g., 'supermarket', 'grocery_store', 'bakery', 'restaurant').
        radius_meters: Search radius in meters (default 2000.0).

    Returns:
        A JSON string containing nearby places with name, formatted address, location, and place types.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key or api_key == "PASTE_KEY_HERE":
        return "Google Maps API Key is missing or unconfigured in GOOGLE_MAPS_API_KEY environment variable."

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.types"
    }
    payload = {
        "includedTypes": [place_type],
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": float(latitude),
                    "longitude": float(longitude)
                },
                "radius": float(radius_meters)
            }
        }
    }
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            places = data.get("places", [])
            if not places:
                return f"No nearby places of type '{place_type}' found within {radius_meters} meters."
            results = []
            for p in places[:5]:
                results.append({
                    "name": p.get("displayName", {}).get("text"),
                    "address": p.get("formattedAddress"),
                    "location": p.get("location"),
                    "types": p.get("types", [])
                })
            return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error searching nearby places: {str(e)}"


def generate_dish_image(
    prompt: str,
    tool_context: ToolContext,
    recipe_title: str = "",
) -> str:
    """Generates an image for a food dish or recipe item using gemini-3.1-flash-lite-image in the global region.

    Saves the image as an artifact in ToolContext and uploads the bytes directly to public Cloud Storage.

    Args:
        prompt: Detailed visual prompt describing the food item or recipe dish to generate.
        tool_context: ADK ToolContext instance injected automatically.
        recipe_title: Optional title of the recipe or dish item.

    Returns:
        The public HTTPS Cloud Storage URL of the uploaded image.
    """
    client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="global")

    image_bytes = None
    mime_type = "image/jpeg"

    try:
        res = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=f"Generate a photograph of {prompt}",
        )
        if res.candidates and res.candidates[0].content and res.candidates[0].content.parts:
            for part in res.candidates[0].content.parts:
                if part.inline_data:
                    image_bytes = part.inline_data.data
                    mime_type = part.inline_data.mime_type or "image/jpeg"
                    break
    except Exception:
        pass

    # Fallback image rendering if model call fails
    if not image_bytes:
        img = Image.new("RGB", (600, 400), color=(44, 62, 80))
        draw = ImageDraw.Draw(img)
        draw.rectangle([10, 10, 590, 390], outline=(230, 126, 34), width=4)
        draw.text((40, 180), recipe_title or prompt[:30], fill=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()
        mime_type = "image/png"

    clean_title = (recipe_title or "dish").lower().replace(" ", "_")[:20]
    ext = "jpg" if "jpeg" in mime_type else "png"
    filename = f"{clean_title}_{uuid.uuid4().hex[:8]}.{ext}"

    # 1. Save artifact with tool_context.save_artifact for Playground Artifacts panel
    if tool_context:
        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        tool_context.save_artifact(filename=filename, artifact=artifact_part)

    # 2. Upload image bytes directly to public Cloud Storage bucket from memory
    storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(image_bytes, content_type=mime_type)

    return f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"


def get_weather(query: str) -> str:
    """Simulates a web search. Use it get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        query: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


# Build A2UI v0.8 system prompt
schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are Smart Pantry Concierge, a helpful culinary assistant. "
        "You help users discover local and public recipes based on ingredients they have in their pantry, "
        "check recipe details, add new recipes to the database, generate dish images using gemini-3.1-flash-lite-image, "
        "fetch meal ideas from public web APIs, geocode addresses, find nearby grocery stores or food markets using Google Maps, "
        "and run Python code safely in a sandbox when complex calculations or data transformations are needed."
    ),
    workflow_description="Analyze the request, call relevant tools, and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "IMPORTANT MEMORY RULE: Pay strict attention to all user allergies, intolerances, and dietary restrictions "
        "(e.g., peanut, gluten, dairy, lactose, shellfish, egg, soy, tree nuts, vegan, vegetarian). "
        "Always remember these allergies across sessions via Memory Bank, and automatically filter out any recipe or food recommendation "
        "that contains ingredients unsafe for the user's remembered allergies. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    code_executor=code_executor,
    tools=[
        PreloadMemoryTool(),
        search_recipes,
        get_recipe_details,
        add_recipe,
        get_public_meal_ideas,
        generate_dish_image,
        geocode_address,
        find_nearby_places,
        get_weather,
        get_current_time,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
