from app import app

# Keep this for local development
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

# This is what Vercel will use
application = app
