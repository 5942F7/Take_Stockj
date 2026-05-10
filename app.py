from __future__ import annotations

from pathlib import Path
import base64
import os

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import requests
import time

app = Flask(__name__)
CORS(app)

_YAHOO_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
_MAX_IMAGE_BYTES = 12 * 1024 * 1024  # 12 MB
_QUOTE_CACHE_TTL_SEC = 8
_quote_cache: dict[str, tuple[float, dict]] = {}

_BASE = Path(__file__).resolve().parent

# 與 fix_take_stockj_all.ps1 內嵌版相同之手機介面；另可由 webview_app.html 覆寫（若存在）
_INDEX_HTML_PATH = _BASE / "webview_app.html"

_FALLBACK_INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>AI股神拍圖版</title>
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: Arial, "Microsoft JhengHei", sans-serif;
            background: radial-gradient(circle at top, #1e293b 0%, #020617 52%, #000 100%);
            color: #fff;
            min-height: 100vh;
        }
        .app { width: 100%; max-width: 520px; margin: 0 auto; min-height: 100vh; padding: 18px; }
        .header { padding: 18px 4px 14px; text-align: center; }
        .logo {
            width: 76px; height: 76px; border-radius: 24px; margin: 0 auto 14px;
            background: linear-gradient(135deg, #22c55e, #16a34a); color: #052e16;
            display: flex; align-items: center; justify-content: center;
            font-size: 34px; font-weight: 900;
            box-shadow: 0 18px 45px rgba(34, 197, 94, 0.28);
        }
        h1 { margin: 0; font-size: 29px; color: #86efac; letter-spacing: 0.5px; }
        .subtitle { margin-top: 8px; color: #cbd5e1; font-size: 14px; line-height: 1.5; }
        .card {
            margin-top: 16px; padding: 18px; border-radius: 22px;
            background: rgba(15, 23, 42, 0.82);
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 20px 60px rgba(0,0,0,0.38);
        }
        .section-title { font-size: 16px; font-weight: 700; margin-bottom: 12px; color: #e5e7eb; }
        .upload-box {
            border: 2px dashed rgba(134, 239, 172, 0.45); border-radius: 18px;
            padding: 20px 14px; text-align: center; background: rgba(34, 197, 94, 0.08);
        }
        .upload-box input { display: none; }
        .upload-btn {
            display: inline-block; padding: 13px 20px; border-radius: 14px;
            background: linear-gradient(135deg, #22c55e, #16a34a); color: #052e16;
            font-weight: 800; cursor: pointer; border: none; font-size: 16px;
        }
        .hint { margin-top: 10px; font-size: 13px; color: #94a3b8; line-height: 1.5; }
        .preview { margin-top: 16px; display: none; }
        .preview img {
            width: 100%; max-height: 360px; object-fit: contain; border-radius: 16px;
            background: #000; border: 1px solid rgba(255,255,255,0.12);
        }
        textarea, input[type="text"] {
            width: 100%; margin-top: 10px; border-radius: 14px;
            border: 1px solid rgba(255,255,255,0.12);
            background: rgba(2, 6, 23, 0.8); color: white; padding: 13px;
            font-size: 15px; outline: none;
        }
        textarea { min-height: 90px; resize: vertical; line-height: 1.5; }
        .main-btn {
            width: 100%; margin-top: 16px; padding: 15px 16px; border-radius: 16px;
            border: none; background: linear-gradient(135deg, #22c55e, #16a34a);
            color: #052e16; font-weight: 900; font-size: 17px; cursor: pointer;
        }
        .main-btn:disabled { opacity: 0.55; cursor: not-allowed; }
        .secondary-btn {
            width: 100%; margin-top: 10px; padding: 12px 14px; border-radius: 14px;
            border: 1px solid rgba(255,255,255,0.16); background: rgba(255,255,255,0.06);
            color: #e5e7eb; font-weight: 700; font-size: 14px; cursor: pointer;
        }
        .status {
            margin-top: 14px; padding: 12px; border-radius: 14px;
            display: none; font-size: 14px; line-height: 1.5;
        }
        .status.info { display: block; background: rgba(59, 130, 246, 0.16); color: #bfdbfe; }
        .status.ok { display: block; background: rgba(34, 197, 94, 0.16); color: #bbf7d0; }
        .status.err { display: block; background: rgba(239, 68, 68, 0.16); color: #fecaca; }
        .result { margin-top: 16px; display: none; }
        .result pre {
            margin: 0; white-space: pre-wrap; word-wrap: break-word;
            background: rgba(0,0,0,0.45); border-radius: 14px; padding: 14px;
            color: #e5e7eb; font-size: 14px; line-height: 1.55; max-height: 420px; overflow: auto;
        }
        .footer { text-align: center; font-size: 12px; color: #64748b; padding: 22px 0 12px; }
        .endpoint-row { margin-top: 14px; }
        .endpoint-row label { display: block; font-size: 13px; color: #94a3b8; margin-bottom: 4px; }
        .badge {
            display: inline-block; margin-top: 8px; padding: 5px 9px; border-radius: 999px;
            font-size: 12px; background: rgba(34,197,94,0.15); color: #bbf7d0;
        }
        .quote-mini { margin-top: 12px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.08); }
        .quote-mini label { font-size: 13px; color: #94a3b8; }
    </style>
</head>
<body>
    <div class="app">
        <div class="header">
            <div class="logo">AI</div>
            <h1>AI股神拍圖版</h1>
            <div class="subtitle">
                上傳股票截圖、K線圖或盤面圖片，讓 AI 協助你整理重點。
            </div>
            <div class="badge">Render API 已連線</div>
        </div>

        <div class="card">
            <div class="section-title">即時報價（選用）</div>
            <div class="quote-mini">
                <label for="stockCode">股票代號</label>
                <input id="stockCode" type="text" inputmode="numeric" maxlength="6" placeholder="例如 2330">
                <button type="button" id="quoteBtn" class="secondary-btn">查詢報價</button>
            </div>
        </div>

        <div class="card">
            <div class="section-title">1. 選擇圖片</div>
            <div class="upload-box">
                <label for="imageInput" class="upload-btn">選擇圖片</label>
                <input id="imageInput" type="file" accept="image/*">
                <div class="hint">可選擇股票截圖、技術線圖、新聞截圖或盤面圖片。</div>
            </div>
            <div id="preview" class="preview">
                <img id="previewImg" alt="圖片預覽">
            </div>
        </div>

        <div class="card">
            <div class="section-title">2. 分析需求</div>
            <textarea id="promptInput" placeholder="例如：請幫我分析這張股票圖的趨勢、支撐壓力、風險和操作建議。">請幫我分析這張股票圖的趨勢、支撐壓力、可能風險與重點觀察。</textarea>
            <div class="endpoint-row">
                <label>分析 API 路徑，可手動修改</label>
                <input id="endpointInput" type="text" value="/api/analyze">
            </div>
            <button id="analyzeBtn" class="main-btn" disabled>開始分析</button>
            <button id="healthBtn" class="secondary-btn">測試 API 狀態</button>
            <div id="status" class="status"></div>
        </div>

        <div id="resultBox" class="card result">
            <div class="section-title">3. 分析結果</div>
            <pre id="resultText"></pre>
        </div>

        <div class="footer">AI股神拍圖版 V10 WebView App</div>
    </div>

    <script>
        const imageInput = document.getElementById("imageInput");
        const preview = document.getElementById("preview");
        const previewImg = document.getElementById("previewImg");
        const analyzeBtn = document.getElementById("analyzeBtn");
        const healthBtn = document.getElementById("healthBtn");
        const quoteBtn = document.getElementById("quoteBtn");
        const stockCode = document.getElementById("stockCode");
        const statusBox = document.getElementById("status");
        const resultBox = document.getElementById("resultBox");
        const resultText = document.getElementById("resultText");
        const promptInput = document.getElementById("promptInput");
        const endpointInput = document.getElementById("endpointInput");

        let selectedFile = null;

        const savedEndpoint = localStorage.getItem("ai_stock_endpoint");
        if (savedEndpoint) endpointInput.value = savedEndpoint;

        endpointInput.addEventListener("change", function () {
            localStorage.setItem("ai_stock_endpoint", endpointInput.value.trim());
        });

        function setStatus(type, text) {
            statusBox.className = "status " + type;
            statusBox.innerText = text;
        }

        function showResult(data) {
            resultBox.style.display = "block";
            if (typeof data === "string") {
                resultText.innerText = data;
                return;
            }
            if (data && typeof data.analysis === "string") {
                var meta = "";
                if (data.engine) meta += "[" + data.engine + "] ";
                resultText.innerText = meta + data.analysis;
                return;
            }
            try {
                resultText.innerText = JSON.stringify(data, null, 2);
            } catch (e) {
                resultText.innerText = String(data);
            }
        }

        quoteBtn.addEventListener("click", async function () {
            const code = (stockCode.value || "").trim();
            if (!code) {
                setStatus("err", "請輸入股票代號。");
                return;
            }
            setStatus("info", "查詢報價中…");
            try {
                const resp = await fetch("/api/quote?code=" + encodeURIComponent(code));
                const data = await resp.json();
                if (!resp.ok) throw new Error(JSON.stringify(data));
                setStatus("ok", "報價已取得");
                showResult(data);
            } catch (e) {
                setStatus("err", "報價失敗：" + e.message);
            }
        });

        imageInput.addEventListener("change", function () {
            const file = imageInput.files && imageInput.files[0];
            if (!file) {
                selectedFile = null;
                analyzeBtn.disabled = true;
                preview.style.display = "none";
                return;
            }
            selectedFile = file;
            analyzeBtn.disabled = false;
            previewImg.src = URL.createObjectURL(file);
            preview.style.display = "block";
            setStatus("ok", "圖片已選擇：" + file.name);
        });

        async function readFileAsBase64(file) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => {
                    const result = reader.result || "";
                    resolve(String(result).split(",")[1] || "");
                };
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
        }

        async function parseResponse(resp) {
            const text = await resp.text();
            try { return JSON.parse(text); } catch (e) { return text; }
        }

        async function tryFormDataEndpoint(endpoint) {
            const form = new FormData();
            form.append("file", selectedFile);
            form.append("image", selectedFile);
            form.append("photo", selectedFile);
            form.append("prompt", promptInput.value || "");
            form.append("question", promptInput.value || "");
            const resp = await fetch(endpoint, { method: "POST", body: form });
            const data = await parseResponse(resp);
            if (!resp.ok) throw new Error("HTTP " + resp.status + " - " + JSON.stringify(data));
            return data;
        }

        async function tryJsonEndpoint(endpoint) {
            const base64 = await readFileAsBase64(selectedFile);
            const payload = {
                image_base64: base64, image: base64,
                prompt: promptInput.value || "", question: promptInput.value || ""
            };
            const resp = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const data = await parseResponse(resp);
            if (!resp.ok) throw new Error("HTTP " + resp.status + " - " + JSON.stringify(data));
            return data;
        }

        analyzeBtn.addEventListener("click", async function () {
            if (!selectedFile) {
                setStatus("err", "請先選擇圖片。");
                return;
            }
            analyzeBtn.disabled = true;
            resultBox.style.display = "none";
            const customEndpoint = endpointInput.value.trim() || "/api/analyze";
            localStorage.setItem("ai_stock_endpoint", customEndpoint);
            const endpoints = [
                customEndpoint, "/api/analyze", "/analyze", "/api/predict",
                "/predict", "/api/upload", "/upload"
            ];
            const uniqueEndpoints = [...new Set(endpoints)];
            setStatus("info", "正在上傳圖片並分析，請稍候...");
            let lastError = null;
            try {
                for (const ep of uniqueEndpoints) {
                    try {
                        setStatus("info", "嘗試呼叫 API：" + ep);
                        const data = await tryFormDataEndpoint(ep);
                        setStatus("ok", "分析完成。使用 API：" + ep);
                        showResult(data);
                        return;
                    } catch (e1) { lastError = e1; }
                }
                for (const ep of uniqueEndpoints) {
                    try {
                        setStatus("info", "改用 JSON Base64 模式呼叫：" + ep);
                        const data = await tryJsonEndpoint(ep);
                        setStatus("ok", "分析完成。使用 API：" + ep);
                        showResult(data);
                        return;
                    } catch (e2) { lastError = e2; }
                }
                throw lastError || new Error("沒有可用 API。");
            } catch (err) {
                setStatus("err",
                    "分析失敗。\\n\\n可能原因：後端分析 API 路徑不正確，或後端尚未實作圖片分析。\\n\\n目前嘗試過：\\n" +
                    uniqueEndpoints.join("\\n") + "\\n\\n最後錯誤：\\n" +
                    (err && err.message ? err.message : String(err)));
            } finally {
                analyzeBtn.disabled = false;
            }
        });

        healthBtn.addEventListener("click", async function () {
            setStatus("info", "正在檢查 API 狀態...");
            try {
                const resp = await fetch("/api/health");
                const data = await parseResponse(resp);
                if (!resp.ok) throw new Error("HTTP " + resp.status);
                setStatus("ok", "API 正常。");
                showResult(data);
            } catch (err) {
                setStatus("err", "API 狀態檢查失敗：" + err.message);
            }
        });
    </script>
</body>
</html>
"""


def _index_html() -> str:
    if _INDEX_HTML_PATH.is_file():
        return _INDEX_HTML_PATH.read_text(encoding="utf-8")
    return _FALLBACK_INDEX_HTML


@app.get("/")
def home():
    return Response(_index_html(), mimetype="text/html; charset=utf-8")


@app.get("/api/health")
def health():
    return jsonify(
        {
            "ok": True,
            "name": "AI股神拍圖版 V10 API",
            "quote_backends": ["twse", "yahoo"],
            "broker_configured": bool(
                os.environ.get("SINOPAC_API_KEY")
                and os.environ.get("SINOPAC_SECRET_KEY")
            ),
            "vision_openai": bool(os.environ.get("OPENAI_API_KEY")),
            "vision_gemini": bool(
                os.environ.get("GEMINI_API_KEY")
                or os.environ.get("GOOGLE_API_KEY")
            ),
        }
    )


def _normalize_stock_code(raw: str) -> str:
    """只保留數字，例如 '2330'、'8069'。"""
    s = raw.strip().upper()
    digits = "".join(ch for ch in s if ch.isdigit())
    return digits[:6] if digits else ""


def _get_quote_cache(code: str) -> dict | None:
    item = _quote_cache.get(code)
    if not item:
        return None
    ts, payload = item
    if time.time() - ts > _QUOTE_CACHE_TTL_SEC:
        _quote_cache.pop(code, None)
        return None
    out = dict(payload)
    out["cached"] = True
    return out


def _set_quote_cache(code: str, payload: dict) -> dict:
    _quote_cache[code] = (time.time(), dict(payload))
    out = dict(payload)
    out["cached"] = False
    return out


def _quote_twse(code: str) -> dict | None:
    channels = [f"tse_{code}.tw", f"otc_{code}.tw"]
    url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
    for ch in channels:
        try:
            r = requests.get(
                url,
                params={
                    "ex_ch": ch,
                    "json": "1",
                    "_": int(time.time() * 1000),
                },
                timeout=8,
                headers={"User-Agent": _YAHOO_UA, "Referer": "https://mis.twse.com.tw/"},
            )
            data = r.json()
            arr = data.get("msgArray") or []
            if arr:
                q = arr[0]
                price = float(q.get("z") or q.get("y") or q.get("o") or 0)
                y = float(q.get("y") or 0)
                high = float(q.get("h") or price)
                low = float(q.get("l") or price)
                if price and y:
                    label = q.get("n") or "—"
                    return {
                        "code": code,
                        "name": label.strip() if isinstance(label, str) else str(label),
                        "price": price,
                        "yesterday": y,
                        "high": high,
                        "low": low,
                        "change": round(price - y, 4),
                        "source": (
                            "TWSE"
                            if ch.startswith("tse")
                            else "TPEx_TWSE接口"
                        ),
                    }
        except Exception:
            continue
    return None


def _quote_yahoo(code: str) -> dict | None:
    """Yahoo Chart API — 對海外雲端主機較友善；依序試 .TW（上市）、.TWO（櫃買／部分上櫃）。"""
    for suffix, market in [(".TW", "Yahoo_TSE"), (".TWO", "Yahoo_OTC")]:
        symbol = f"{code}{suffix}"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        try:
            r = requests.get(
                url,
                params={"range": "5d", "interval": "1d"},
                timeout=12,
                headers={"User-Agent": _YAHOO_UA, "Accept": "application/json"},
            )
            if r.status_code != 200:
                continue
            payload = r.json()
            result = payload.get("chart", {}).get("result") or []
            if not result:
                continue
            meta = result[0].get("meta") or {}
            price = meta.get("regularMarketPrice")
            if price is None:
                price = meta.get("postMarketPrice") or meta.get("preMarketPrice")
            prev_close = meta.get("chartPreviousClose") or meta.get(
                "previousClose"
            )
            if prev_close is None and result[0].get("indicators", {}).get(
                "quote"
            ):
                q0 = result[0]["indicators"]["quote"][0]
                closes = q0.get("close") or []
                for c in reversed(closes):
                    if c is not None:
                        prev_close = c
                        break
            if price is None or prev_close is None:
                continue
            pc = float(prev_close)
            pr = float(price)
            hi = meta.get("regularMarketDayHigh") or pr
            lo = meta.get("regularMarketDayLow") or pr
            name = (
                meta.get("shortName")
                or meta.get("longName")
                or meta.get("symbol")
                or code
            )
            return {
                "code": code,
                "name": name,
                "price": round(pr, 4),
                "yesterday": round(pc, 4),
                "high": float(hi),
                "low": float(lo),
                "change": round(pr - pc, 4),
                "source": market,
                "yahoo_symbol": symbol,
            }
        except Exception:
            continue
    return None


def _extract_image_and_prompt():
    prompt = ""
    if request.content_type and "application/json" in request.content_type:
        body = request.get_json(silent=True) or {}
        prompt = (
            body.get("prompt") or body.get("question") or ""
        ).strip()
        b64 = body.get("image_base64") or body.get("image")
        if b64:
            try:
                # 允許 "data:image/...;base64,..."
                raw_b64 = b64.split(",")[-1] if "," in str(b64) else b64
                data = base64.standard_b64decode(raw_b64)
            except Exception as e:
                return None, None, "", f"無法解析 image_base64: {e}"
            mime = body.get("mime_type") or "image/jpeg"
            return data, mime, prompt, None
        return None, None, prompt, None

    prompt = (
        request.form.get("prompt") or request.form.get("question") or ""
    ).strip()
    for key in ("file", "image", "photo"):
        fstor = request.files.get(key)
        if fstor and fstor.filename:
            data = fstor.read()
            mime = (
                fstor.mimetype
                or "image/jpeg"
            )
            return data, mime, prompt, None
    return None, None, prompt, None


def _vision_openai(image_bytes: bytes, mime: str, prompt: str) -> tuple[str | None, str | None]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None, None
    model = os.environ.get(
        "OPENAI_VISION_MODEL", "gpt-4o-mini"
    )
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    user_line = prompt or (
        "你是熟悉台股的助理。請根據圖片內容整理：標的／走勢觀察、可能支撐壓力區、 "
        "風險與注意事項。若圖上不完整請說明。回覆請用繁體中文。"
        "\n【免責】以上為資訊整理，非投資建議。"
    )
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_line},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{b64}",
                        },
                    },
                ],
            }
        ],
        "max_tokens": 2500,
    }
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    if r.status_code >= 400:
        try:
            err = r.json()
        except Exception:
            err = r.text[:800]
        return None, str(err)
    out = r.json()
    choices = out.get("choices") or []
    if not choices:
        return None, "OpenAI 回傳無 choices"
    msg = choices[0].get("message", {})
    txt = msg.get("content") or ""
    return str(txt).strip(), None


def _vision_gemini(image_bytes: bytes, mime: str, prompt: str) -> tuple[str | None, str | None]:
    key = (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
    )
    if not key:
        return None, None
    model = os.environ.get("GEMINI_VISION_MODEL", "gemini-1.5-flash")
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    user_line = prompt or (
        "你是熟悉台股的助理。請根據圖片內容整理重點觀察與風險。"
        "回覆請用繁體中文，並於最後註明此為資訊整理非投資建議。"
    )
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
    body = {
        "contents": [
            {
                "parts": [
                    {"text": user_line},
                    {
                        "inline_data": {
                            "mime_type": mime or "image/jpeg",
                            "data": b64,
                        }
                    },
                ]
            }
        ]
    }
    r = requests.post(url, params={"key": key}, json=body, timeout=120)
    if r.status_code >= 400:
        try:
            err = r.json()
        except Exception:
            err = r.text[:800]
        return None, str(err)
    out = r.json()
    parts = (
        out.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [])
    )
    texts = [p.get("text", "") for p in parts if p.get("text")]
    txt = "".join(texts).strip()
    return txt or None, None


@app.post("/api/analyze")
def analyze():
    """圖片 + 提示詞；優先 OPENAI_API_KEY，其次 GEMINI_API_KEY / GOOGLE_API_KEY。"""
    img, mime, prompt, err = _extract_image_and_prompt()
    if err:
        return jsonify({"error": err}), 400
    if not img:
        return (
            jsonify(
                {
                    "error": "未收到圖片",
                    "hint": '請使用 multipart（欄位 file / image）或 JSON 傳 image_base64',
                }
            ),
            400,
        )
    if len(img) > _MAX_IMAGE_BYTES:
        return (
            jsonify(
                {"error": f"圖片過大（上限 {_MAX_IMAGE_BYTES // (1024*1024)} MB）"}
            ),
            413,
        )

    if not os.environ.get("OPENAI_API_KEY") and not (
        os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    ):
        return (
            jsonify(
                {
                    "error": "伺服器尚未設定視覺分析",
                    "setup": (
                        "在 Render → Environment 新增任一：OPENAI_API_KEY，"
                        "或 GEMINI_API_KEY（也可用 GOOGLE_API_KEY）。"
                    ),
                    "optional": {"OPENAI_VISION_MODEL": "gpt-4o-mini", "GEMINI_VISION_MODEL": "gemini-1.5-flash"},
                }
            ),
            503,
        )

    txt, openai_err = _vision_openai(img, mime, prompt)
    if txt:
        return jsonify({"ok": True, "engine": "openai", "analysis": txt})

    if openai_err and os.environ.get("OPENAI_API_KEY"):
        # OpenAI 有設金鑰但失敗 — 仍試 Gemini（若設定）
        pass

    txt2, gem_err = _vision_gemini(img, mime, prompt)
    if txt2:
        return jsonify({"ok": True, "engine": "gemini", "analysis": txt2})

    # 不回傳上游完整錯誤，避免洩漏第三方服務細節
    return (
        jsonify(
            {
                "ok": False,
                "error": "影像分析服務暫時不可用，請稍後再試。",
                "hint": "請確認 Render 的 OPENAI_API_KEY 或 GEMINI_API_KEY 已正確設定。",
            }
        ),
        502,
    )


@app.get("/api/quote")
def quote():
    code = _normalize_stock_code(request.args.get("code", ""))
    if not code:
        return jsonify({"error": "missing or invalid code"}), 400
    if len(code) < 4:
        return jsonify({"error": "stock code too short"}), 400

    cached = _get_quote_cache(code)
    if cached:
        return jsonify(cached)

    # 1) 台灣證交所即時接口（若在雲端被擋則自動改用 Yahoo）
    tw = _quote_twse(code)
    if tw:
        return jsonify(_set_quote_cache(code, tw))

    yh = _quote_yahoo(code)
    if yh:
        return jsonify(_set_quote_cache(code, yh))

    return (
        jsonify(
            {
                "error": "無法取得報價，請確認股票代號正確（上市如 2330、上櫃／櫃買請仍輸入數字）",
                "code": code,
            }
        ),
        502,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
