from flask import Blueprint, render_template, session, redirect, url_for, request
from functools import wraps
from cpl.models import Admin

bp = Blueprint("admin", __name__, url_prefix="/admin")

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return decorated


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        admin = Admin.query.filter_by(username=username).first()

        if admin and admin.check_password(password):
            session["is_admin"] = True
            return redirect(url_for("main.home"))   # redirect to your homepage

        return "Invalid admin credentials"

    return render_template("admin/login.html")


@bp.route("/logout")
def logout():
    session.pop("is_admin", None)
    return redirect(url_for("main.home"))
