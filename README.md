# Dividend Tracker Web Application

A web application for tracking dividend-paying financial assets with live valuations and monthly income projections.

## Features

- **Live Stock Prices** - Real-time price data from Yahoo Finance
- **Dividend Tracking** - Annual dividend amounts based on historical payments
- **Portfolio Valuation** - Total portfolio value calculated from current prices
- **Monthly Breakdown** - See which months dividends are paid with expandable details
- **CSV Import** - Bulk import assets from CSV files
- **Mobile-Friendly** - Responsive design optimized for mobile devices

## Architecture

| Component | Technology |
|-----------|------------|
| Backend | Python / Flask |
| Database | MongoDB |
| Frontend | Vanilla JS / CSS |
| Deployment | Docker / Docker Compose |
| CI/CD | Jenkins |

## Quick Start

```bash
# Clone the repository
git clone <repo-url>
cd dividend-tracker

# Start the application
docker compose up -d

# Access at http://localhost:5050/finance/
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGO_URI` | `mongodb://mongo:27017/` | MongoDB connection string |
| `SECRET_KEY` | (auto-generated) | Flask session secret key |
| `ALPHA_VANTAGE_KEY` | (none) | Optional API key for fallback data source |

### Data Sources

The application fetches stock data from multiple sources with automatic fallback:

1. **Yahoo Finance** (primary) - No API key required
2. **Alpha Vantage** (fallback) - Requires free API key from [alphavantage.co](https://www.alphavantage.co/support/#api-key)

If Yahoo Finance fails or rate-limits, the app automatically tries Alpha Vantage. Get a free API key (25 requests/day) and set it via environment variable:

```yaml
environment:
  - ALPHA_VANTAGE_KEY=your_api_key_here
```

### Port Configuration

Default port is `5050`. Change in `docker-compose.yml`:

```yaml
ports:
  - "5050:5000"  # Change 5050 to desired port
```

### Reverse Proxy

The application is designed to run behind a reverse proxy at `/finance`. Example nginx configuration:

```nginx
location /finance {
    proxy_pass http://localhost:5050;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/finance/` | Main application UI |
| GET | `/finance/api/assets` | List all assets with live data |
| POST | `/finance/api/assets` | Add new asset |
| PUT | `/finance/api/assets/<symbol>` | Update asset quantity |
| DELETE | `/finance/api/assets/<symbol>` | Remove asset |
| POST | `/finance/api/import` | Import assets from CSV |
| GET | `/finance/api/summary` | Portfolio summary |
| GET | `/finance/api/monthly` | Monthly dividend breakdown |

## CSV Import

Import assets in bulk using CSV files. The importer supports flexible column names:

**Supported column names:**
- Symbol: `symbol`, `ticker`, `stock`
- Quantity: `quantity`, `qty`, `shares`, `amount`

**Example CSV:**
```csv
symbol,quantity
AAPL,10
MSFT,25.5
SCHD,100
VYM,50
```

If an asset already exists, the quantity will be added to the existing amount.

## Data Caching

Stock data is cached for 5 minutes to reduce API calls to Yahoo Finance. Cache is automatically cleared when importing new assets.

## Development

### Run Locally (without Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Start MongoDB (required)
docker run -d -p 27017:27017 mongo:7

# Run the application
python app.py
```

### Project Structure

```
dividend-tracker/
├── app.py              # Flask application
├── templates/
│   └── index.html      # Frontend UI
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container image
├── docker-compose.yml  # Container orchestration
├── Jenkinsfile         # CI/CD pipeline
└── README.md           # Documentation
```

## Deployment with Jenkins

The included `Jenkinsfile` provides a simple pipeline:

1. **Build** - Builds the Docker image
2. **Deploy** - Stops existing containers and starts new ones

Point Jenkins to the repository and run the pipeline to deploy.

## Troubleshooting

### Yahoo Finance Rate Limiting

If you see errors fetching stock data, Yahoo Finance may be rate limiting requests. The application will use cached data when available. Wait a few minutes and refresh.

### Port Already in Use

If port 5050 is in use, change the port mapping in `docker-compose.yml` or stop the conflicting service.

### MongoDB Connection Issues

Ensure the MongoDB container is running:
```bash
docker compose ps
```

## License

MIT
