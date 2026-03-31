---
title: "feat: Add drag-drop upload and improved status text"
type: feat
status: completed
date: 2026-03-31
origin: docs/brainstorms/2026-03-31-ux-polish-requirements.md
---

# feat: Add drag-drop upload and improved status text

## Overview

為兩個頁面（移除背景、圖片轉 3D）加上拖放上傳支援和更明確的處理狀態文字，提升使用者體驗。

## Problem Frame

目前上傳只有點擊選檔，缺少拖放支援。處理中的回饋只有 spinner + 簡短文字，使用者不確定目前進行到哪一步。(see origin: docs/brainstorms/2026-03-31-ux-polish-requirements.md)

## Requirements Trace

- R1. 兩個頁面的上傳區域都支援拖放檔案
- R2. 拖放時顯示視覺提示（邊框高亮）
- R3. 拖放的檔案需經過與點擊上傳相同的驗證
- R4. 處理中時禁用拖放
- R5. 移除背景頁面：顯示「正在移除背景，請稍候…」
- R6. 圖片轉 3D 頁面：顯示「步驟 1/2：正在移除背景…」和「步驟 2/2：正在轉換 3D 模型…」
- R7. 狀態文字取代現有簡短文字，不加 progress bar

## Scope Boundaries

- 不做進度百分比
- 不做多檔案拖放
- 不抽取共用的 DragDropZone 元件 — 兩個頁面各自處理即可，避免過度抽象

## Context & Research

### Relevant Code and Patterns

- `RemoveBg.jsx` — 使用 `handleFileChange` 處理選檔，`loading` state 控制 disabled
- `ImageTo3D.jsx` — 使用 `handleFileChange` 處理選檔，`step` state 控制多步驟流程
- `validation.js` — 現有 `validateFile(f)` 函式，可直接用於拖放檔案
- `index.css` — `.upload-form` 和 `.file-label` 是上傳區域的樣式
- 兩個元件結構幾乎相同：file state → handleFileChange → validate → set file

## Key Technical Decisions

- **不抽取共用元件**：兩個頁面的拖放邏輯只有 ~15 行 event handler，複製比抽象更簡單。如果未來有第三個上傳點再考慮抽取。
- **用 dragenter counter 防止閃爍**：子元素會觸發 dragleave，用 counter 追蹤進出次數，避免高亮閃爍。
- **拖放區域 = 整個 `.upload-form`**：不另加容器，直接在現有 form 上加 drag event。

## Open Questions

### Deferred to Implementation

- 拖放高亮的確切視覺效果（邊框顏色、虛線）可在實作時微調

## Implementation Units

- [x] **Unit 1: RemoveBg 拖放上傳 + 狀態文字**

**Goal:** RemoveBg 頁面支援拖放上傳並改善處理狀態文字

**Requirements:** R1, R2, R3, R4, R5, R7

**Dependencies:** None

**Files:**
- Modify: `frontend/src/RemoveBg.jsx`
- Modify: `frontend/src/index.css`

**Approach:**
- 加入 `dragOver` state 控制高亮
- 在 form 上加 `onDragEnter`, `onDragLeave`, `onDragOver`, `onDrop` handler
- 用 dragenter counter 防止子元素觸發的 dragleave 閃爍
- `onDrop` 取第一個檔案，呼叫 `validateFile`，通過後 `setFile`
- `loading` 為 true 時，drop handler 直接 return（R4）
- 處理中按鈕文字改為「正在移除背景，請稍候…」（R5）
- CSS 加上 `.upload-form.drag-over` 樣式（邊框高亮 + 背景色變化）

**Patterns to follow:**
- 現有 `handleFileChange` 的驗證和 state 設定邏輯

**Test scenarios:**
- Happy path: 拖放一個 PNG 檔案 → file state 被設定，顯示預覽
- Edge case: 拖放非圖片檔案 → 顯示驗證錯誤訊息
- Edge case: 拖放多個檔案 → 只取第一個
- Error path: 處理中拖放檔案 → 被忽略，不改變 state

**Verification:**
- 拖放 PNG/JPEG/WebP 可以上傳並顯示預覽
- 拖放時有視覺高亮提示
- 處理中按鈕顯示「正在移除背景，請稍候…」
- 處理中拖放被禁用

- [x] **Unit 2: ImageTo3D 拖放上傳 + 狀態文字**

**Goal:** ImageTo3D 頁面支援拖放上傳並改善兩步驟狀態文字

**Requirements:** R1, R2, R3, R4, R6, R7

**Dependencies:** Unit 1（CSS 已在 Unit 1 加好）

**Files:**
- Modify: `frontend/src/ImageTo3D.jsx`

**Approach:**
- 與 Unit 1 相同的拖放邏輯（dragOver state, counter, event handlers）
- `isRemoving || isConverting` 時禁用拖放（R4）
- 移除背景按鈕文字改為「步驟 1/2：正在移除背景…」（R6）
- 轉換 3D 按鈕文字改為「步驟 2/2：正在轉換 3D 模型…」（R6）

**Patterns to follow:**
- Unit 1 的拖放實作
- 現有 `step` state 的條件邏輯

**Test scenarios:**
- Happy path: 拖放一個 PNG 檔案 → file state 被設定
- Edge case: 移除背景中拖放 → 被忽略
- Edge case: 轉換 3D 中拖放 → 被忽略
- Happy path: 移除背景時按鈕顯示「步驟 1/2：正在移除背景…」
- Happy path: 轉換 3D 時按鈕顯示「步驟 2/2：正在轉換 3D 模型…」

**Verification:**
- 拖放功能與 RemoveBg 頁面行為一致
- 兩步驟的狀態文字正確顯示步驟編號

## System-Wide Impact

- **Interaction graph:** 只影響前端兩個元件，不涉及後端或 API 變更
- **Unchanged invariants:** 後端 API、檔案驗證邏輯、AbortController 行為均不變

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| dragenter/dragleave 在子元素上閃爍 | 用 counter 追蹤進出次數 |

## Sources & References

- **Origin document:** [docs/brainstorms/2026-03-31-ux-polish-requirements.md](docs/brainstorms/2026-03-31-ux-polish-requirements.md)
- Related code: `frontend/src/RemoveBg.jsx`, `frontend/src/ImageTo3D.jsx`, `frontend/src/validation.js`
