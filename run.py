import os
from app import app
from backend.app.config import FLASK_PORT, FLASK_DEBUG

if __name__ == "__main__":
    print("=" * 60)
    print("  Initializing Modular Air Quality Dashboard")
    print("=" * 60)
    
    # Check ML models loading output from __init__
    
    # Run the server
    import socket
    try:
        hostip = socket.gethostbyname(socket.gethostname())
    except:
        hostip = "127.0.0.1"
        
    print(f" * Running on http://127.0.0.1:{FLASK_PORT}")
    if hostip != "127.0.0.1":
        print(f" * Running on http://{hostip}:{FLASK_PORT}")
    print("Press CTRL+C to quit")
    
    # Let Werkzeug print its own warning/banner by omitting custom ones when running app.run()
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=FLASK_DEBUG)
