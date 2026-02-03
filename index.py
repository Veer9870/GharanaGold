from app import create_app
import os

app = create_app(os.getenv('FLASK_CONFIG') or 'default')

# This is needed because Vercel looks for the 'app' variable by default
# but if you need to expose it specifically or handle something before 
# the request, you can do it here.
