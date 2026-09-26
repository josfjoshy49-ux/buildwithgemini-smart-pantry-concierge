"""Seed script to populate initial recipes in Firestore for Smart Pantry Concierge."""

from google.cloud import firestore

# CRITICAL: Hardcode project ID string. Do NOT use google.auth.default() or GOOGLE_CLOUD_PROJECT
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-02-94350be92468"

def seed_database():
    db = firestore.Client(project=FIRESTORE_PROJECT_ID)
    recipes_ref = db.collection("recipes")

    seeded_recipes = [
        {
            "doc_id": "lemon-garlic-pasta",
            "title": "Lemon Garlic Pasta",
            "description": "Light and refreshing pasta dish with zesty lemon, garlic, and fresh herbs.",
            "ingredients": ["spaghetti", "lemon", "garlic", "olive oil", "parmesan", "parsley"],
            "dietary_tags": ["vegetarian"],
            "prep_time_minutes": 15,
            "instructions": "1. Boil pasta. 2. Sauté garlic in olive oil. 3. Toss pasta with garlic oil, lemon juice, parmesan, and fresh parsley.",
        },
        {
            "doc_id": "chickpea-avocado-salad",
            "title": "Chickpea Avocado Salad",
            "description": "Protein-packed salad featuring ripe avocados, chickpeas, and a lime vinaigrette.",
            "ingredients": ["chickpeas", "avocado", "cherry tomatoes", "cucumber", "lime", "cilantro"],
            "dietary_tags": ["vegan", "gluten-free", "vegetarian"],
            "prep_time_minutes": 10,
            "instructions": "1. Rinse chickpeas. 2. Dice avocado, tomatoes, and cucumber. 3. Combine in a bowl and dress with fresh lime juice, olive oil, salt, and cilantro.",
        },
        {
            "doc_id": "classic-tomato-basil-soup",
            "title": "Classic Tomato Basil Soup",
            "description": "Rich and creamy tomato soup infused with fresh basil leaves.",
            "ingredients": ["canned tomatoes", "onion", "garlic", "vegetable broth", "heavy cream", "basil"],
            "dietary_tags": ["vegetarian", "gluten-free"],
            "prep_time_minutes": 25,
            "instructions": "1. Sauté onion and garlic. 2. Add tomatoes and broth, simmer for 20 mins. 3. Blend until smooth, stir in cream and fresh basil.",
        },
    ]

    for recipe in seeded_recipes:
        doc_id = recipe.pop("doc_id")
        recipes_ref.document(doc_id).set(recipe)
        print(f"Seeded recipe: {doc_id} -> {recipe['title']}")

    print("\nDatabase seeding completed successfully!")

if __name__ == "__main__":
    seed_database()
