import uuid
import os, requests
from flask import jsonify
from bson import ObjectId
from flask import Flask, request, jsonify, render_template
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required
)
from flask_pymongo import PyMongo
from bson import ObjectId
from openai import OpenAI
from flasgger import Swagger
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__, template_folder='.')
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET")
app.config["MONGO_URI"]      = os.getenv("MONGO_URI")
Swagger(app)
jwt = JWTManager(app)
mongo = PyMongo(app)
apis = mongo.db.apis
# ---------- UI ----------
@app.route("/")
def home(): return render_template("interface.html")
@app.route("/update")
def update_page():
    return render_template("update.html")

@app.route("/delete")
def delete_page():
    return render_template("delete.html")

# ---------- AUTH ----------
@app.post("/login")
def login():
    token = create_access_token(identity=str(uuid.uuid4()))
    return jsonify(access_token=token)
# ---------- REST CRUD ----------
@app.route('/apis', methods=['GET'])
def list_apis():
    apis = list(mongo.db.apis.find())
    for api in apis:
        api['_id'] = str(api['_id'])
    return jsonify({'apis': apis})
@app.get("/api/v1/items")
def all_items():
    out = [{**doc, "_id": str(doc["_id"])} for doc in apis.find()]
    return jsonify(out)
@app.post("/api/v1/items")
@jwt_required()
def add_item():
    body = request.json
    _id  = apis.insert_one(body).inserted_id
    return jsonify(id=str(_id)), 201
@app.put("/api/v1/items/<item_id>")
@jwt_required()
def edit_item(item_id):
    body   = request.json
    apis.update_one({"_id": ObjectId(item_id)}, {"$set": body})
    return jsonify(msg="updated")
@app.delete("/api/v1/items/<item_id>")
@jwt_required()
def drop_item(item_id):
    apis.delete_one({"_id": ObjectId(item_id)})
    return jsonify(msg="deleted")
# ---------- AI ----------
@app.post("/api/v1/items/<item_id>/summary")
def summarize(item_id):
    """Return a 2‑line summary of the item's description using Cohere’s /v1/summarize API"""
    # 1️⃣ Fetch the document
    doc = apis.find_one({"_id": ObjectId(item_id)})
    if not doc:
        return jsonify(error="not found"), 404

    # 2️⃣ Call Cohere
    headers = {
        "Authorization": f"Bearer {os.getenv('COHERE_API_KEY')}",
        "Content-Type": "application/json"
    }
    payload = {
        "text": doc["description"],
        "model": "command",          # default, fine for free tier
        "length": "short",           # short / medium / long / auto
        "format": "paragraph"        # paragraph / bullets / auto
    }
    response = requests.post(
        "https://api.cohere.com/v1/summarize",
        headers=headers,
        json=payload,
        timeout=30
    )

    if response.status_code != 200:
        # Cohere will return JSON with an `error` field; forward it upstream
        return jsonify(error=response.text), response.status_code

    cohere_json = response.json()    # → { "summary": "..." } :contentReference[oaicite:0]{index=0}
    return jsonify(summary=cohere_json["summary"])
@app.get("/api/v1/items/<item_id>")
def get_item(item_id):
    doc = apis.find_one({"_id": ObjectId(item_id)})
    if not doc:
        return jsonify(error="not found"), 404
    doc["_id"] = str(doc["_id"])
    return jsonify(doc)

if __name__ == "__main__":
    app.run(debug=True)
