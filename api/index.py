"""Vercel serverless entry point.

Vercel imports the module-level ``app`` object from this file.
"""
from app import create_app


app = create_app()
