from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import Dict, List
from market_data_fetcher import get_market_data, get_valid_symbols

app = FastAPI(title="Market Data API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "online", "timestamp": datetime.utcnow().isoformat()}

@app.get("/symbols", response_model=List[str])
async def available_symbols():
    """Get list of available stock symbols"""
    symbols = get_valid_symbols()
    return list(symbols)

@app.get("/market-data/{symbol}")
async def market_data(symbol: str) -> Dict:
    """Get 3-minute market data for a specific symbol"""
    df = get_market_data(symbol, debug=False)
    
    if df is None:
        raise HTTPException(status_code=404, detail=f"No data found for symbol {symbol}")
    
    data = {
        "symbol": symbol,
        "last_updated": datetime.utcnow().isoformat(),
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

@app.get("/market-data/{symbol}/latest")
async def latest_price(symbol: str) -> Dict:
    """Get just the latest price for a symbol"""
    df = get_market_data(symbol, debug=False)
    
    if df is None:
        raise HTTPException(status_code=404, detail=f"No data found for symbol {symbol}")
    
    latest = df.iloc[-1]
    return {
        "symbol": symbol,
        "timestamp": latest.name.strftime('%Y-%m-%d %H:%M:%S'),
        "price": latest["close"],
        "volume": latest["volume"]
    }