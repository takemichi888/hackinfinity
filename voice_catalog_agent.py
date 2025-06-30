import speech_recognition as sr
import json
import spacy
from gtts import gTTS
import streamlit as st
import os
import base64

# Load NLP model with error handling
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    st.error("Error: Please run 'python -m spacy download en_core_web_sm' to install the model.")
    st.stop()

# Initialize or load catalog
catalog_file = "catalog.json"
if os.path.exists(catalog_file):
    with open(catalog_file, "r", encoding="utf-8") as f:
        catalog = json.load(f)
else:
    catalog = [
        {"title": "Cotton Saree", "price": 500, "category": "Clothing", "ordered": False, "quantity": 5},
        {"title": "Rice Bag", "price": 300, "category": "Groceries", "ordered": False, "quantity": 10}
    ]
    with open(catalog_file, "w", encoding="utf-8") as f:
        json.dump(catalog, f)

# Session state for role and interaction
if 'role' not in st.session_state:
    st.session_state.role = None
if 'listening' not in st.session_state:
    st.session_state.listening = False
if 'response' not in st.session_state:
    st.session_state.response = None
if 'audio_playing' not in st.session_state:
    st.session_state.audio_playing = False

# Process voice command with longer listening time
def process_voice_command():
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            st.write("Adjusting for ambient noise...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            st.write("Listening... Please speak (up to 10 seconds).")
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=10)
            query = recognizer.recognize_google(audio).lower()
            return query
    except sr.UnknownValueError:
        return "Sorry, I didn’t catch that."
    except sr.RequestError:
        return "Error: Speech recognition service unavailable."
    except Exception as e:
        return f"Error: {str(e)}"

# Suggest category
def suggest_category(title):
    categories = {"saree": "Clothing", "rice": "Groceries", "phone": "Electronics", "cotton": "Clothing", "mobile": "Electronics", "iron": "Electronics"}
    return next((cat for key, cat in categories.items() if key in title.lower()), "Uncategorized")

# Add to catalog with single sentence
def add_to_catalog(command):
    if "add" in command:
        parts = command.split("for")
        if len(parts) < 2:
            return "Please use format 'add [quantity] [item] for [price] and category [category]'."
        
        item_part = parts[0].replace("add", "").strip()
        price_category_part = parts[1].strip()
        
        # Extract quantity (default to 1 if not specified)
        quantity_words = [w for w in item_part.split() if w.isdigit()]
        quantity = int(quantity_words[0]) if quantity_words else 1
        item_part = " ".join(w for w in item_part.split() if not w.isdigit())
        
        price_words = [w for w in price_category_part.split() if any(c.isdigit() for c in w)]
        price = next((int(''.join(filter(str.isdigit, w))) for w in price_words if any(c.isdigit() for c in w)), 0)
        if price == 0:
            return "Invalid or no price detected. Please include a numeric price."

        category_start = price_category_part.lower().find("and category")
        if category_start != -1:
            category = " ".join(price_category_part[category_start + len("and category"):].strip().split())
            if not category:
                category = suggest_category(item_part)
        else:
            category = suggest_category(item_part)

        title_words = item_part.split()
        product = {"title": " ".join(title_words).strip(), "price": price, "category": category, "ordered": False, "quantity": quantity}
        catalog.append(product)
        with open(catalog_file, "w", encoding="utf-8") as f:
            json.dump(catalog, f)
        return f"Added {product['title']} at {product['price']} per item in {product['category']} with quantity {product['quantity']}."

# Remove item
def remove_item(command):
    if "remove" in command:
        doc = nlp(command)
        title_words = [token.text.lower() for token in doc if token.pos_ in ["NOUN", "PROPN"]]
        for i, item in enumerate(catalog):
            if any(word in item["title"].lower() for word in title_words):
                removed_item = catalog.pop(i)
                with open(catalog_file, "w", encoding="utf-8") as f:
                    json.dump(catalog, f)
                return f"Removed {removed_item['title']} from the catalog."
        return "Item not found."
    return "Please say 'remove [item]' to remove an item."

# Assign quantity
def assign_quantity(command):
    if "assign no.of items" in command:
        parts = command.split("to")
        if len(parts) < 2:
            return "Please use format 'assign quantity [number] to [item]'."
        
        quantity_part, item_part = parts[0].strip(), parts[1].strip()
        quantity = next((int(w) for w in quantity_part.split() if w.isdigit()), 0)
        if quantity <= 0:
            return "Invalid quantity. Please say a positive number."
        
        doc = nlp(item_part)
        title_words = [token.text.lower() for token in doc if token.pos_ in ["NOUN", "PROPN"]]
        for item in catalog:
            if any(word in item["title"].lower() for word in title_words):
                item["quantity"] = quantity
                with open(catalog_file, "w", encoding="utf-8") as f:
                    json.dump(catalog, f)
                return f"Assigned quantity {quantity} to {item['title']}."
        return "Item not found."
    return "Please say 'assign quantity [number] to [item]' to set quantity."

# Change price
def change_price(command):
    if "change price of" in command:
        parts = command.split("to")
        if len(parts) < 2:
            return "Please use format 'change price of [item] to [price]'."
        
        item_part = parts[0].replace("change price of", "").strip()
        price_part = parts[1].strip()
        price = next((int(w) for w in price_part.split() if w.isdigit()), 0)
        if price <= 0:
            return "Invalid price. Please say a positive number."
        
        doc = nlp(item_part)
        title_words = [token.text.lower() for token in doc if token.pos_ in ["NOUN", "PROPN"]]
        for item in catalog:
            if any(word in item["title"].lower() for word in title_words):
                item["price"] = price
                with open(catalog_file, "w", encoding="utf-8") as f:
                    json.dump(catalog, f)
                return f"Changed price of {item['title']} to {price} per item."
        return "Item not found."
    return "Please say 'change price of [item] to [price]' to change the price."

# Search items with flexible input
def search_items(command):
    doc = nlp(command)
    title_words = [token.text.lower() for token in doc if token.pos_ in ["NOUN", "PROPN"]]
    price_words = [w for w in command.split() if any(c.isdigit() for c in w)]
    price = next((int(''.join(filter(str.isdigit, w))) for w in price_words if any(c.isdigit() for c in w)), None)
    category_words = [w for w in command.split() if w in ["clothing", "groceries", "electronics"]]

    matches = []
    for item in catalog:
        if (not title_words or any(word in item["title"].lower() for word in title_words)) and \
           (price is None or item["price"] == price) and \
           (not category_words or item["category"].lower() in [cat.lower() for cat in category_words]) and \
           not item["ordered"] and item["quantity"] > 0:
            matches.append(item)
    if matches:
        return f"Found items: {', '.join([f'{item['title']} at {item['price']} per item ({item['quantity']} available)' for item in matches])}"
    return "No matching items found."

# Place order with quantity and price
def place_order(command):
    doc = nlp(command)
    title_words = [token.text.lower() for token in doc if token.pos_ in ["NOUN", "PROPN"]]
    quantity_words = [w for w in command.split() if w.isdigit()]
    quantity_to_order = int(quantity_words[0]) if quantity_words else 1

    for item in catalog:
        if any(word in item["title"].lower() for word in title_words) and not item["ordered"] and item["quantity"] >= quantity_to_order:
            if item["quantity"] - quantity_to_order < 0:
                return "Insufficient quantity available."
            item["quantity"] -= quantity_to_order  # Ensure quantity is reduced by ordered amount
            total_price = quantity_to_order * item["price"]
            if item["quantity"] == 0:
                item["ordered"] = True
                status = " (out of stock)"
            else:
                status = ""
            with open(catalog_file, "w", encoding="utf-8") as f:
                json.dump(catalog, f)  # Save the updated catalog
            return f"Ordered {quantity_to_order} {item['title']}(s) at {item['price']} per item. Total price: {total_price}{status}."
    return "Item not found, out of stock, or insufficient quantity."

# Generate audio response
def generate_audio_response(text):
    tts = gTTS(text=text, lang="en")
    audio_file = "response.mp3"
    tts.save(audio_file)
    with open(audio_file, "rb") as f:
        base64_audio = base64.b64encode(f.read()).decode('ascii')  # Encode binary to base64
    return base64_audio

# Streamlit UI with interactive AI agent
st.title("Voice-to-Catalog Agent")

# Initial voice prompt for role selection
if st.session_state.role is None:
    initial_prompt = "Please select whether you are a Seller or Buyer."
    base64_audio = generate_audio_response(initial_prompt)
    st.markdown(f'''
        <audio id="audio-player" src="data:audio/mp3;base64,{base64_audio}" autoplay>
            Your browser does not support the audio element.
        </audio>
        <button onclick="document.getElementById('audio-player').pause();">Stop</button>
    ''', unsafe_allow_html=True)
    # os.remove(audio_file)  # Removed to avoid permission error

# Role selection
role = st.selectbox("Are you a Seller or Buyer?", ["Select Role", "Seller", "Buyer"], key="role_select")
if role == "Select Role":
    st.write("Please choose 'Seller' or 'Buyer' to proceed.")
else:
    if st.session_state.role != role:  # Role changed
        st.session_state.role = role
        st.session_state.listening = False
        st.session_state.response = None
        st.session_state.audio_playing = False

    if st.button("Speak"):
        st.session_state.listening = True
        command = process_voice_command()
        st.write(f"You said: {command}")

        if st.session_state.role == "Seller":
            if "add" in command:
                st.session_state.response = add_to_catalog(command)
            elif "remove" in command:
                st.session_state.response = remove_item(command)
            elif "assign quantity" in command:
                st.session_state.response = assign_quantity(command)
            elif "change price of" in command:
                st.session_state.response = change_price(command)
            else:
                st.session_state.response = "Please say 'add [quantity] [item] for [price] and category [category]', 'remove [item]', 'assign quantity [number] to [item]', or 'change price of [item] to [price]'."
        elif st.session_state.role == "Buyer":
            if "search" in command:
                st.session_state.response = search_items(command)
            elif "place order" in command or "order" in command:
                st.session_state.response = place_order(command)
            else:
                st.session_state.response = "Please say 'search [item/category] at [price]' or 'place order [quantity] [item]'."

        st.write(st.session_state.response)
        base64_audio = generate_audio_response(st.session_state.response)
        st.markdown(f'''
            <audio id="audio-player" src="data:audio/mp3;base64,{base64_audio}" autoplay>
                Your browser does not support the audio element.
            </audio>
            <button onclick="document.getElementById('audio-player').pause();">Stop</button>
        ''', unsafe_allow_html=True)
        # os.remove(audio_file)  # Removed to avoid permission error
        st.session_state.listening = False  # Stop listening after response

    if st.button("Stop"):
        st.session_state.listening = False
        st.session_state.audio_playing = False
        st.markdown('<script>document.getElementById("audio-player").pause();</script>', unsafe_allow_html=True)
        st.write("Interaction stopped.")

    st.write("Current Catalog:", {i: item for i, item in enumerate(catalog)})