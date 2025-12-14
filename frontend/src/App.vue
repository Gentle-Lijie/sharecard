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

        <section v-if="result" class="result">
            <div class="meta">
                <h2>{{ result.title }}</h2>
                <p class="url">{{ result.url }}</p>
                <h3>Summary</h3>
                <p>{{ result.summary }}</p>
                <details>
                    <summary>展开网页文本 (截断展示)</summary>
                    <p>{{ truncatedContent }}</p>
                </details>
            </div>
            <div class="card-preview">
                <p class="label">分享卡片预览</p>
                <img :src="result.card_image_base64" alt="share card" />
            </div>
        </section>
    </main>
</template>

<script setup>
    import { ref, computed } from 'vue'
    import { apiClient } from './api'

    const url = ref('')
    const loading = ref(false)
    const error = ref('')
    const result = ref(null)

    const truncatedContent = computed(() => {
        if (!result.value?.content) return ''
        return result.value.content.slice(0, 600) + (result.value.content.length > 600 ? '…' : '')
    })

    const submit = async () => {
        error.value = ''
        if (!url.value) return
        loading.value = true
        try {
            const resp = await apiClient.post('/api/summarize', { url: url.value })
            result.value = resp.data
        } catch (err) {
            result.value = null
            error.value = err?.response?.data?.detail || err.message || '请求失败'
        } finally {
            loading.value = false
        }
    }
</script>

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
        width: 100%;
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
</style>
