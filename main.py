from core.factory import create_api_app


app = create_api_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app)
