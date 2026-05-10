from pathlib import Path

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import requests
import time

app = Flask(__name__)
CORS(app)

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
    return jsonify({"ok": True, "name": "AI股神拍圖版 V10 API"})


@app.post("/api/analyze")
def analyze():
    """收到圖片與提示詞；目前為輕量回應（未接 Vision API 時仍可確認上傳流程正常）。"""
    prompt = ""
    if request.is_json:
        body = request.get_json(silent=True) or {}
        prompt = (body.get("prompt") or body.get("question") or "").strip()
    else:
        prompt = (
            request.form.get("prompt") or request.form.get("question") or ""
        ).strip()
    has_file = bool(request.files and len(request.files) > 0)
    return jsonify(
        {
            "status": "demo",
            "message": (
                "伺服器已收到請求。"
                "完整圖片 AI 解讀需在 Render 環境設定 OpenAI／Gemini 等 Vision API 後實作。"
            ),
            "has_image_upload": has_file,
            "prompt_received": bool(prompt),
            "quote_hint": "可先使用「查詢報價」：GET /api/quote?code=2330",
        }
    )


@app.get("/api/quote")
def quote():
    code = request.args.get("code", "").strip()
    if not code:
        return jsonify({"error": "missing code"}), 400
    channels = [f"tse_{code}.tw", f"otc_{code}.tw"]
    for ch in channels:
        url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
        try:
            r = requests.get(
                url,
                params={
                    "ex_ch": ch,
                    "json": "1",
                    "_": int(time.time() * 1000),
                },
                timeout=5,
                headers={"User-Agent": "Mozilla/5.0"},
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
                    return jsonify(
                        {
                            "code": code,
                            "name": q.get("n") or "自選股",
                            "price": price,
                            "yesterday": y,
                            "high": high,
                            "low": low,
                            "change": round(price - y, 2),
                            "source": "TWSE" if ch.startswith("tse") else "TPEx",
                        }
                    )
        except Exception:
            pass
    return jsonify({"error": "quote failed or code not found"}), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
