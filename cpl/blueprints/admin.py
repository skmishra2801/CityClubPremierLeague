from flask import Blueprint, render_template


bp = Blueprint("admin", __name__)


@bp.route("/")
def dashboard():

    return render_template("admin/dashboard.html", )


@bp.route("/news/new", methods=["GET", "POST"])
def create_news():

    return render_template("admin/news_form.html")
