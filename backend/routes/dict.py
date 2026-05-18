"""
Dictionary proxy API
GET /api/dict/lookup?word=xxx   — proxy to Youdao jsonapi
GET /api/dict/fanyi?word=xxx    — proxy to Youdao fanyi (fallback for proper nouns)
GET /api/dict/audio?key=xxx     — proxy to Youdao dictvoice audio
"""
import httpx
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/dict", tags=["dict"])

YOUDAO_URL  = "https://dict.youdao.com/jsonapi"
FANYI_URL   = "https://fanyi.youdao.com/translate"
AUDIO_URL   = "https://dict.youdao.com/dictvoice"
YOUDAO_PARAMS_BASE = {"doctype": "json", "keyfrom": "webdict", "jsonversion": 1}


@router.get("/lookup")
async def lookup_word(word: str = Query(..., min_length=1, max_length=100)):
    params = {**YOUDAO_PARAMS_BASE, "q": word}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(YOUDAO_URL, params=params)
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Dictionary request timed out")
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/fanyi")
async def fanyi_word(word: str = Query(..., min_length=1, max_length=100)):
    params = {"i": word, "from": "en", "to": "zh-CHS", "doctype": "json"}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(FANYI_URL, params=params)
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Fanyi request timed out")
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/audio")
async def proxy_audio(
    key: str = Query(..., min_length=1, max_length=200),
    type: int = Query(1, ge=0, le=2)
):
    """
    Proxy audio from Youdao dictvoice
    key: audio key (e.g., "noma")
    type: 0=auto, 1=UK, 2=US
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(AUDIO_URL, params={"audio": key, "type": type})
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "audio/mpeg")
            return StreamingResponse(
                iter([resp.content]),
                media_type=content_type,
                headers={"Cache-Control": "public, max-age=86400"},
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Audio request timed out")
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
