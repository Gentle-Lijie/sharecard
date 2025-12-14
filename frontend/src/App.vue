<template>
    <main class="card">
        <header class="hero">
            <div>
                <p class="eyebrow">ShareCard · 一键生成分享卡片</p>
                <h1>输入一个 URL，抓取网页并自动总结</h1>
                <p class="sub">后端 Python + OpenAI，总结内容并生成带二维码的卡片。通过 Docker 一键运行。</p>
            </div>
        </header>

        <section class="input-area">
            <label for="url">网页链接</label>
            <div class="input-row">
                <input id="url" v-model="url" type="url" placeholder="https://example.com/article"
                    @keyup.enter="submit" />
                <button :disabled="loading || !url" @click="submit">
                    {{ loading ? '处理中…' : '获取与生成' }}
                </button>
            </div>
            <p v-if="error" class="error">{{ error }}</p>
        </section>

        <section v-if="partial || result" class="result">
            <div class="meta">
                <h2>{{ partial?.title || result?.title }}</h2>
                <p class="url">{{ decodeUrl(partial?.url || result?.url) }}</p>

                <h3>网页正文（截断）</h3>
                <p>{{ (partial?.content || result?.content) ? (partial?.content || result?.content).slice(0, 600) +
                    ((partial?.content || result?.content)?.length > 600 ? '…' : '') : '' }}</p>

                <div v-if="loadingAI" style="margin-top:12px;">
                    <strong>正在调用 API 生成摘要……</strong>
                </div>

                <div v-if="result">
                    <h3>Summary</h3>
                    <p>{{ result.summary }}</p>
                </div>
            </div>
            <div class="card-preview" v-if="partial || result">
                <p class="label">分享卡片预览</p>

                <div class="card-wrapper">
                    <div class="card-html" :class="selectedTheme" ref="cardEl">
                        <img v-if="(partial?.favicon_base64 || result?.favicon_base64)"
                            :src="partial?.favicon_base64 || result?.favicon_base64" class="favicon" alt="favicon" />
                        <div class="card-content">
                            <div class="card-title" :contenteditable="editing" ref="titleEl" @input="onTitleInput"
                                @keydown="onTitleKeydown" v-html="editedTitle"></div>
                            <h4 class="card-url" :contenteditable="editing">{{ decodeUrl(partial?.url || result?.url) }}
                            </h4>
                            <p class="card-desc" :contenteditable="editing" ref="descEl">{{ editedDesc }}</p>
                        </div>
                        <img v-if="(partial?.qr_image_base64 || result?.qr_image_base64)"
                            :src="partial?.qr_image_base64 || result?.qr_image_base64" class="card-qr" alt="qr" />
                    </div>

                    <div class="card-controls">
                        <label>主题:
                            <select v-model="selectedTheme">
                                <option value="theme-dark">深色</option>
                                <option value="theme-light">浅色</option>
                                <option value="theme-accent">渐变</option>
                            </select>
                        </label>
                        <button @click="toggleEdit">{{ editing ? '保存' : '编辑' }}</button>
                        <button v-if="editing" @click="cancelEdit">取消</button>
                        <button @click="exportPNG" :disabled="exporting">导出 PNG</button>
                        <button @click="exportPDF" :disabled="exporting">导出 PDF</button>
                    </div>
                </div>
            </div>
        </section>
    </main>
</template>

<script setup>
    import { ref, computed, nextTick } from 'vue'
    import { apiClient } from './api'
    import html2canvas from 'html2canvas'
    import { saveAs } from 'file-saver'
    import { jsPDF } from 'jspdf'

    const url = ref('')
    const loading = ref(false)
    const loadingFetch = ref(false)
    const loadingAI = ref(false)
    const error = ref('')
    const result = ref(null)
    const partial = ref(null) // holds title/content after fetch
    const editing = ref(false)
    const editedTitle = ref('')
    const editedDesc = ref('')
    const selectedTheme = ref('theme-dark')
    const titleEl = ref(null)
    const descEl = ref(null)
    const cardEl = ref(null)
    const exporting = ref(false)

    const toggleEdit = () => {
        if (!editing.value) {
            // start editing
            editing.value = true
            // Prefer the finalized result (summary) when available; otherwise fall back to partial fetch
            editedTitle.value = result.value?.title || partial.value?.title || ''
            editedDesc.value = result.value?.summary || partial.value?.content || ''
            // focus later via refs
            nextTick(() => {
                if (titleEl.value) {
                    // ensure the DOM shows current edited title and focus
                    titleEl.value.innerHTML = editedTitle.value || ''
                    titleEl.value.focus()
                }
                if (descEl.value) {
                    descEl.value.innerHTML = editedDesc.value || ''
                }
            })
        } else {
            // save
            // read edited content from DOM if possible (preserve HTML/line breaks)
            if (titleEl.value) editedTitle.value = titleEl.value.innerHTML
            if (descEl.value) editedDesc.value = descEl.value.innerHTML
            editing.value = false
            // write back to result (so displayed summary/card use edited content)
            if (result.value) {
                result.value.title = editedTitle.value
                result.value.summary = editedDesc.value
            } else if (partial.value) {
                partial.value.title = editedTitle.value
                partial.value.content = editedDesc.value
            }
        }
    }

    const onTitleInput = (e) => {
        // keep editedTitle in sync as user types (preserve newlines)
        editedTitle.value = e.target.innerHTML
    }

    const onTitleKeydown = (e) => {
        if (e.key === 'Enter') {
            // Prevent the browser from inserting a new block element (<div> or <p>)
            e.preventDefault()
            // insert a <br> at caret
            insertLineBreakAtCaret()
            // update the reactive value
            if (titleEl.value) editedTitle.value = titleEl.value.innerHTML
        }
    }

    const insertLineBreakAtCaret = () => {
        const sel = window.getSelection()
        if (!sel || !sel.rangeCount) return
        const range = sel.getRangeAt(0)
        // create a <br> element
        const br = document.createElement('br')
        // insert the <br>
        range.deleteContents()
        range.insertNode(br)
        // move caret after the <br>
        range.setStartAfter(br)
        range.collapse(true)
        sel.removeAllRanges()
        sel.addRange(range)
    }

    const cancelEdit = () => {
        // revert edited fields to the currently displayed values (result or partial)
        if (result.value) {
            editedTitle.value = result.value.title
            editedDesc.value = result.value.summary
        } else if (partial.value) {
            editedTitle.value = partial.value.title
            editedDesc.value = partial.value.content
        }
        editing.value = false
    }

    const truncatedContent = computed(() => {
        if (!result.value?.content) return ''
        return result.value.content.slice(0, 600) + (result.value.content.length > 600 ? '…' : '')
    })

    const decodeUrl = (str) => {
        try {
            return decodeURIComponent(str);
        } catch (e) {
            return str; // fallback if decoding fails
        }
    };

    const submit = async () => {
        error.value = ''
        result.value = null
        partial.value = null
        if (!url.value) return

        console.log('Submitting URL:', url.value)


        const decoded = decodeUrl(url.value);
        url.value = decoded;
        console.log('Decoded URL:', decoded);

        // Step 1: fetch title and truncated content quickly
        loadingFetch.value = true
        try {
            const respFetch = await apiClient.get('/api/fetch', { params: { url: url.value } })
            partial.value = respFetch.data
        } catch (err) {
            error.value = err?.response?.data?.detail || err.message || '抓取网页失败'
            loadingFetch.value = false
            return
        } finally {
            loadingFetch.value = false
        }

        // Step 2: call OpenAI (show progress)
        loadingAI.value = true
        try {
            const resp = await apiClient.post('/api/summarize', { url: url.value })
            result.value = resp.data
            // initialize edited fields from result
            editedTitle.value = result.value.title
            editedDesc.value = result.value.summary
        } catch (err) {
            result.value = null
            error.value = err?.response?.data?.detail || err.message || '调用 OpenAI 失败'
        } finally {
            loadingAI.value = false
        }
    }

    const exportPNG = async () => {
        if (!cardEl.value) return
        exporting.value = true
        try {
            // scale up for better quality
            const canvas = await html2canvas(cardEl.value, { useCORS: true, backgroundColor: null, scale: 2 })
            canvas.toBlob((blob) => {
                if (!blob) return
                const name = (editedTitle.value || result.value?.title || 'sharecard').replace(/[^a-z0-9-_\u4e00-\u9fa5]/gi, '_')
                saveAs(blob, `${name}.png`)
            }, 'image/png')
        } catch (err) {
            console.error('导出 PNG 失败', err)
            error.value = '导出 PNG 失败：' + (err?.message || err)
        } finally {
            exporting.value = false
        }
    }

    const exportPDF = async () => {
        if (!cardEl.value) return
        exporting.value = true
        try {
            const canvas = await html2canvas(cardEl.value, { useCORS: true, backgroundColor: null, scale: 2 })
            const dataUrl = canvas.toDataURL('image/png')
            // create PDF sized to the canvas pixels
            const pdf = new jsPDF({ unit: 'px', format: [canvas.width, canvas.height] })
            pdf.addImage(dataUrl, 'PNG', 0, 0, canvas.width, canvas.height)
            const name = (editedTitle.value || result.value?.title || 'sharecard').replace(/[^a-z0-9-_\u4e00-\u9fa5]/gi, '_')
            pdf.save(`${name}.pdf`)
        } catch (err) {
            console.error('导出 PDF 失败', err)
            error.value = '导出 PDF 失败：' + (err?.message || err)
        } finally {
            exporting.value = false
        }
    }
</script>

/*
字体说明：
- 请把字体文件放到 `frontend/public/fonts/` 下：
- Aptos.woff2 （英文字体）
- HarmonyOS_Sans.woff2 （中文字体）
如果你已通过 CDN 或系统安装字体，可调整以下 @font-face 的 src 或移除。
*/

<style>
    @font-face {
        font-family: 'Aptos';
        src: url('/fonts/Aptos.woff2') format('woff2');
        font-weight: 100 900;
        font-style: normal;
        font-display: swap;
        /* 拉丁/ASCII 范围优先由 Aptos 处理 */
        unicode-range: U+0000-00FF, U+0100-024F, U+1E00-1EFF;
    }

    @font-face {
        font-family: 'HarmonyOS Sans';
        src: url('/fonts/HarmonyOS_Sans.woff2') format('woff2');
        font-weight: 100 900;
        font-style: normal;
        font-display: swap;
        /* CJK 范围由 HarmonyOS Sans 处理 */
        unicode-range: U+4E00-9FFF, U+3400-4DBF, U+20000-2A6DF;
    }

    /* 全局字体优先级：英文使用 Aptos，中文使用 HarmonyOS Sans（由 unicode-range 控制） */
    html,
    body {
        font-family: 'Aptos', 'HarmonyOS Sans', sans-serif;
    }
</style>

<style scoped>
    .card {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 20px;
        padding: 24px;
        backdrop-filter: blur(8px);
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
    }

    .hero h1 {
        margin: 8px 0 6px;
        font-size: 28px;
    }

    .eyebrow {
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #8b95a5;
        font-weight: 600;
        margin: 0;
    }

    .sub {
        color: #a5b4c7;
    }

    .input-area {
        margin-top: 18px;
        display: grid;
        gap: 10px;
    }

    .input-row {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
    }

    input {
        flex: 1;
        min-width: 260px;
        padding: 12px 14px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.12);
        background: rgba(255, 255, 255, 0.03);
        color: #e2e8f0;
        font-size: 16px;
    }

    button {
        background: linear-gradient(135deg, #3b82f6, #06b6d4);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 12px 18px;
        font-weight: 700;
        transition: transform 0.1s ease, filter 0.1s ease;
    }

    button:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }

    button:not(:disabled):hover {
        transform: translateY(-1px);
        filter: brightness(1.05);
    }

    .error {
        color: #fca5a5;
        margin: 0;
    }

    .result {
        margin-top: 24px;
        display: grid;
        gap: 20px;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    }

    .meta {
        background: rgba(255, 255, 255, 0.03);
        border-radius: 16px;
        padding: 16px;
        border: 1px solid rgba(255, 255, 255, 0.06);
    }

    .meta h2 {
        margin: 0;
    }

    .meta .url {
        color: #94a3b8;
        word-break: break-all;
    }

    .card-preview {
        background: rgba(255, 255, 255, 0.03);
        border-radius: 16px;
        padding: 16px;
        border: 1px solid rgba(255, 255, 255, 0.06);
        text-align: center;
    }

    .card-preview img {
        /* width: 100%; */
        height: auto;
        border-radius: 14px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        background: #0b1220;
    }

    .card-preview .label {
        color: #93c5fd;
        font-weight: 700;
        margin: 0 0 10px;
    }

    /* Card HTML styling */
    .card-wrapper {
        display: flex;
        gap: 12px;
        align-items: flex-start;
        flex-wrap: wrap;
    }

    .card-html {
        width: 320px;
        /* 2:3 ratio -> width 320 height 480 */
        height: 380px;
        border-radius: 24px;
        padding: 18px;
        box-sizing: border-box;
        position: relative;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        overflow: hidden;
    }

    .card-html.theme-dark {
        background: linear-gradient(180deg, #111827, #0b1220);
        color: #e6eef8;
    }

    .card-html.theme-light {
        background: #ffffff;
        color: #0b1220;
        border: 1px solid #e2e8f0;
    }

    .card-html.theme-accent {
        background: linear-gradient(135deg, #7c3aed, #06b6d4);
        color: white;
    }

    .card-html .favicon {
        position: absolute;
        right: 12px;
        top: 12px;
        width: 36px;
        height: 36px;
        border-radius: 8px;
        object-fit: contain;
        background: rgba(255, 255, 255, 0.06);
    }

    .card-content {
        padding-top: 12px;
    }

    .card-title {
        margin: 0 0 8px 0;
        font-size: 20px;
        line-height: 1.1;
        font-weight: 700;
    }

    .card-url {
        margin: 0 0 12px 0;
        font-size: 12px;
        opacity: 0.8;
        word-break: break-all;
    }

    .card-desc {
        text-align: left;
        text-indent: 2em;
        white-space: pre-wrap;
        margin: 0;
        font-size: 16px;
        opacity: 0.95;
        overflow: hidden;
    }

    .card-qr {
        /* position: absolute; */
        align-self: center;
        /* justify-self: unset; */
        right: 12px;
        bottom: 12px;
        width: 50%;
        /* height: 64px; */
        border-radius: 8px;
        background: transparent;
        padding: 0;
        box-sizing: border-box;
        object-fit: cover;
        border: 2px solid rgba(255, 255, 255, 0.92);
        box-shadow: 0 6px 18px rgba(2, 6, 23, 0.45);
    }

    .card-controls {
        display: flex;
        gap: 8px;
        align-items: center;
        margin-top: 8px;
    }

    .card-title[contenteditable="true"],
    .card-desc[contenteditable="true"] {
        outline: 2px dashed rgba(255, 255, 255, 0.12);
        /* padding: 4px; */
    }
</style>
