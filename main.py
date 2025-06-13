from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, Cookie
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
import json
import hashlib
import os


# JWT Config
SECRET_KEY = "your_secret_key_here"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://todo-list-with-jwt.onrender.com/"],  # Change to your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

# --- User Management ---
def get_users():
    if not os.path.exists("C:/Users/LENOVO/Desktop/vs/digitem/jwt/users.json"):
        return {}
    with open("users.json") as f:
        return json.load(f)

def set_user(username, password):
    users = get_users()
    users[username] = hashlib.sha256(password.encode()).hexdigest()
    with open("users.json", "w") as f:
        json.dump(users, f)

def verify_user(username, password):
    users = get_users()
    hashed = hashlib.sha256(password.encode()).hexdigest()
    return username in users and users[username] == hashed

# --- JWT Helpers ---
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_token_from_cookie_or_header(
    request: Request,
    access_token: str = Cookie(None)
):
    # Try to get token from cookie
    if access_token and access_token.startswith("Bearer "):
        return access_token.split(" ", 1)[1]
    # Try to get token from Authorization header
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth.split(" ", 1)[1]
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

def get_current_username(token: str = Depends(get_token_from_cookie_or_header)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return username
    except JWTError:
        raise credentials_exception

def get_todo_file(username):
    return f"todos_{username}.json"

# --- Routes ---
@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
async def register(request: Request):
    form = await request.form()
    username = form["username"]
    password = form["password"]
    users = get_users()
    if username in users:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Username already exists"})
    set_user(username, password)
    return RedirectResponse("/login", status_code=303)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user_valid = verify_user(form_data.username, form_data.password)
    if not user_valid:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": form_data.username})
    response = JSONResponse({"access_token": access_token, "token_type": "bearer"})
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=60*60,  # 1 hour
        samesite="lax"
    )
    return response

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, username: str = Depends(get_current_username)):
    todo_file = get_todo_file(username)
    try:
        with open(todo_file) as f:
            data = json.load(f)
    except:
        data = {}
    sorted_items = sorted(
        data.items(),
        key=lambda item: int(item[1].get("priority", 9999))
    )
    sorted_data = {k: v for k, v in sorted_items}
    return templates.TemplateResponse("todolist.html", {"request": request, "tododict": sorted_data, "username": username})

@app.get("/api/todos")
async def api_todos(request: Request, username: str = Depends(get_current_username)):
    todo_file = get_todo_file(username)
    try:
        with open(todo_file) as f:
            data = json.load(f)
    except:
        data = {}
    return JSONResponse(data)

@app.post("/add")
async def add_todo(request: Request, username: str = Depends(get_current_username)):
    todo_file = get_todo_file(username)
    try:
        with open(todo_file) as f:
            data = json.load(f)
    except:
        data = {}
    formdata = await request.form()
    newdata = {}
    i = 1
    for id in data:
        newdata[str(i)] = data[id]
        i += 1
    newdata[str(i)] = {
        "name": formdata["newtodo"],
        "priority": formdata["priority"]
    }
    with open(todo_file, 'w') as f:
        json.dump(newdata, f)
    return RedirectResponse("/", 303)

@app.get("/delete/{id}")
async def delete_todo(request: Request, id: str, username: str = Depends(get_current_username)):
    todo_file = get_todo_file(username)
    try:
        with open(todo_file) as f:
            data = json.load(f)
    except:
        data = {}
    if id in data:
        del data[id]
        with open(todo_file, 'w') as f:
            json.dump(data, f)
    return RedirectResponse("/", 303)

@app.post("/toggle_done/{id}")
async def toggle_done(id: str, username: str = Depends(get_current_username)):
    todo_file = get_todo_file(username)
    try:
        with open(todo_file) as f:
            data = json.load(f)
    except:
        data = {}
    if id in data:
        data[id]["done"] = not data[id].get("done", False)
        with open(todo_file, 'w') as f:
            json.dump(data, f)
    return {"success": True}
