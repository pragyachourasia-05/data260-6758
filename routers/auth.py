import time

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_302_FOUND


router = APIRouter()
templates = Jinja2Templates(directory="templates")

VALID_USERNAME = "admin"
VALID_PASSWORD = "password"

IDLE_TIMEOUT_SECONDS = 300


def get_active_user(request: Request):
    user = request.session.get("user")
    last_activity = request.session.get("last_activity")

    if not user or not last_activity:
        return None

    if time.time() - last_activity > IDLE_TIMEOUT_SECONDS:
        request.session.clear()
        return None

    request.session["last_activity"] = time.time()
    return user


@router.get("/")
def home(request: Request):
    user = get_active_user(request)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": user,
        },
    )


@router.get("/login")
def login_page(request: Request):
    user = get_active_user(request)
    error = request.query_params.get("error")

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "user": user,
            "error": error,
        },
    )


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if username == VALID_USERNAME and password == VALID_PASSWORD:
        now = time.time()
        request.session["user"] = username
        request.session["last_activity"] = now

        return RedirectResponse(
            url="/dashboard",
            status_code=HTTP_302_FOUND,
        )

    return RedirectResponse(
        url="/login?error=invalid",
        status_code=HTTP_302_FOUND,
    )


@router.get("/dashboard")
def dashboard(request: Request):
    user = get_active_user(request)

    if not user:
        return RedirectResponse(
            url="/login",
            status_code=HTTP_302_FOUND,
        )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
        },
    )


@router.get("/logout")
def logout(request: Request):
    request.session.clear()

    return RedirectResponse(
        url="/",
        status_code=HTTP_302_FOUND,
    )