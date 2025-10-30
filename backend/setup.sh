#!/bin/bash
# Quick setup script for the Social Media API

set -e

echo "🚀 Setting up Social Media API..."

# Install dependencies
echo "📦 Installing dependencies..."
uv sync

# Run migrations
echo "🗄️  Running database migrations..."
uv run python manage.py migrate

# Create superuser prompt
echo ""
echo "👤 Create an admin user for the Django admin panel?"
read -p "Create superuser? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    uv run python manage.py createsuperuser
fi

# Create team and API key
echo ""
echo "🔑 Let's create your first team and API key..."
read -p "Enter team name: " TEAM_NAME
read -p "Enter API key name: " KEY_NAME

uv run python manage.py create_apikey "$TEAM_NAME" --name "$KEY_NAME" --create-team

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the server, run:"
echo "  uv run python manage.py runserver"
echo ""
echo "API will be available at:"
echo "  http://localhost:8000/api/"
echo ""
echo "Interactive docs at:"
echo "  http://localhost:8000/api/docs"
