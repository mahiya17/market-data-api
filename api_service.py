from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
from typing import Dict, List, Optional
from market_data_fetcher import get_market_data, get_valid_symbols, test_dappier_connection
import asyncio
from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    api_version: str = "1.0.0"
    services: Dict[str, Dict[str, str]]
    symbols_count: int
    last_successful_fetch: Optional[str] = None

app = FastAPI(
    title="Market Data API",
    description="Real-time 3-minute market data API service",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state for health monitoring
last_successful_data_fetch = None

async def check_services_health() -> Dict[str, Dict[str, str]]:
    """Check health of all dependent services"""
    services_status = {
        "main_api": {"status": "healthy", "message": "Service is running"},
        "dappier_connection": {"status": "unknown", "message": "Not checked"}
    }
    
    # Test Dappier connection
    try:
        dappier_status = await asyncio.to_thread(test_dappier_connection)
        if dappier_status:
            services_status["dappier_connection"] = {
                "status": "healthy",
                "message": "Connected successfully"
            }
        else:
            services_status["dappier_connection"] = {
                "status": "degraded",
                "message": "Connection issues detected"
            }
    except Exception as e:
        services_status["dappier_connection"] = {
            "status": "unhealthy",
            "message": f"Connection failed: {str(e)}"
        }
    
    return services_status

@app.get("/", response_model=HealthResponse)
async def root():
    """Enhanced health check endpoint providing comprehensive service status"""
    services_health = await check_services_health()
    symbols = get_valid_symbols()
    
    overall_status = "online"
    if any(service["status"] == "unhealthy" for service in services_health.values()):
        overall_status = "degraded"
    
    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "api_version": "1.0.0",
        "services": services_health,
        "symbols_count": len(symbols),
        "last_successful_fetch": last_successful_data_fetch
    }

@app.get("/privacy")
async def privacy_policy():
    """Privacy Policy endpoint"""
    return {
        "privacy_policy": {
            "last_updated": "2024-02-09",
            "policy": [
                "This API provides public market data with no personal data collection.",
                "No personal information is collected, stored, or processed.",
                "Only publicly available stock market data is served.",
                "This service does not use cookies or tracking mechanisms.",
                "All data provided is for informational purposes only."
            ],
            "contact": "For questions about this privacy policy, please create an issue on the project repository."
        }
    }

@app.get("/symbols", response_model=List[str])
async def available_symbols():
    """Get list of available stock symbols"""
    try:
        symbols = get_valid_symbols()
        if not symbols:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to fetch symbols, service may be degraded"
            )
        return list(symbols)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service error: {str(e)}"
        )

@app.get("/market-data/{symbol}")
async def market_data(symbol: str) -> Dict:
    """Get 3-minute market data for a specific symbol"""
    global last_successful_data_fetch
    
    try:
        df = get_market_data(symbol, debug=False)
        
        if df is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No data found for symbol {symbol}"
            )
        
        last_successful_data_fetch = datetime.utcnow().isoformat()
        
        data = {
            "symbol": symbol,
            "last_updated": last_successful_data_fetch,
            "data": {
                "timestamp": df.index.strftime('%Y-%m-%d %H:%M:%S').tolist(),
                "open": df['open'].tolist(),
                "high": df['high'].tolist(),
                "low": df['low'].tolist(),
                "close": df['close'].tolist(),
                "volume": df['volume'].tolist()
            }
        }
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service error: {str(e)}"
        )

@app.get("/market-data/{symbol}/latest")
async def latest_price(symbol: str) -> Dict:
    """Get just the latest price for a symbol"""
    try:
        df = get_market_data(symbol, debug=False)
        
        if df is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No data found for symbol {symbol}"
            )
        
        latest = df.iloc[-1]
        return {
            "symbol": symbol,
            "timestamp": latest.name.strftime('%Y-%m-%d %H:%M:%S'),
            "price": latest["close"],
            "volume": latest["volume"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service error: {str(e)}"
        )