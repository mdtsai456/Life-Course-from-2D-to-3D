---
date: 2026-03-30
topic: rewrite-bg-removal-and-3d
---

# 重寫去背景 + 2D to 3D 功能

## Problem Frame

Life-Course-Remove-Background-main 專案中已有去背景和 Image-to-3D 功能，但程式碼隨功能疊加變得複雜（還包含 voice clone 等不相關功能）。需要在新 repo (chennai) 中重新撰寫這兩個功能，只保留去背景 + 2D to 3D，程式碼更乾淨簡潔。

## Requirements

**後端**
- R1. FastAPI 後端，提供 `/api/remove-background` endpoint（接受 PNG/JPEG/WebP，回傳去背景 PNG）
- R2. FastAPI 後端，提供 `/api/image-to-3d` endpoint（接受 PNG，回傳 GLB）
- R3. 3D 轉換暫時使用 mock 實作（回傳有效的空 GLB），之後再替換為真實推理模型
- R4. 檔案驗證：magic bytes 偵測、10MB 大小限制
- R5. 適當的錯誤處理與 HTTP 狀態碼（413、415、500、503）

**前端**
- R6. React + Vite 前端，兩個功能頁面（tab 或 route 切換）
- R7. 去背景頁面：上傳圖片 → 顯示原圖與去背景結果 → 可下載
- R8. Image to 3D 頁面：兩步驟流程（先去背景 → 再轉 3D）
- R9. 3D 模型使用 `<model-viewer>` 顯示，可旋轉、可下載 GLB
- R10. 基本的載入狀態與錯誤訊息顯示

**通用**
- R11. 繁體中文 UI 文字與錯誤訊息
- R12. 先完成後端，再完成前端

## Success Criteria

- 後端 API 可獨立啟動並回應正確格式
- 前端可上傳圖片、顯示去背景結果、顯示 3D 模型（mock）
- 程式碼簡潔，沒有不必要的抽象

## Scope Boundaries

- 不包含 voice clone 功能
- 不包含拖拽上傳、剪貼簿貼上等進階上傳方式（先做基本的 file input）
- 不包含真實 3D 推理模型整合（之後另外處理）
- 不做 CI/CD、Docker、部署設定

## Key Decisions

- 維持 FastAPI + React + Vite 技術棧：與原專案一致，降低認知負擔
- 先後端再前端：確保 API 穩定後再接前端
- Mock 3D 優先：先跑通整個流程，真實模型之後再接
- 簡單為上：不過度設計，不加不需要的抽象

## Next Steps

→ `/ce:plan` for structured implementation planning
