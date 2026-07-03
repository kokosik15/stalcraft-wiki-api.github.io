import uvicorn
import os

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"http://127.0.0.1:{port}/docs")
    
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=port,
        reload=True,
        workers=1
    )