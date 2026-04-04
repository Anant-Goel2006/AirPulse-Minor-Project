from flask import Blueprint, render_template

views_bp = Blueprint("views_bp", __name__)

@views_bp.route("/")
def index():
    return render_template("index.html")

@views_bp.route("/analytics")
def analytics():
    return render_template("analytics.html")
