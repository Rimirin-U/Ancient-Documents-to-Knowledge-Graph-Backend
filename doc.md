# API 文档

## 基础信息
- 基地址: `http://localhost:3000`
- API 版本: v1
- 所有请求和响应均为 JSON 格式
- 除 `/register` 和 `/login` 外，所有端点都需要 Bearer Token 认证

---

## 认证说明

### Token 获取
通过登录接口获得 JWT Token，有效期为 24 小时。

### Token 使用
所有受保护的 API 请求都需在请求头中包含：
```
Authorization: Bearer {access_token}
```

---

## API 端点

### 测试接口

#### GET /api
测试接口，返回简单的问候信息。

**请求**
```
GET /api
```

**响应**
```
"Hello, World!"
```

---

## 认证路由 (前缀: /api/v1/auth)

### POST /api/v1/auth/register
用户注册端点。

**请求体**
```json
{
  "username": "user@example.com",
  "password": "password123"
}
```

**成功响应** (200)
```json
{
  "success": true,
  "message": "注册成功",
  "userId": 1,
  "username": "user@example.com"
}
```

**失败响应** (400/409)
```json
{
  "detail": "用户名已存在"
}
```

---

### POST /api/v1/auth/login
用户登录端点，获取 JWT Token。

**请求体**
```json
{
  "username": "user@example.com",
  "password": "password123"
}
```

**成功响应** (200)
```json
{
  "success": true,
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": 1,
  "username": "user@example.com"
}
```

**失败响应** (401)
```json
{
  "detail": "用户名或密码错误"
}
```

---

### POST /api/v1/auth/logout
用户退出登录端点。

**请求头**
```
Authorization: Bearer {access_token}
```

**响应** (200)
```json
{
  "success": true,
  "message": "logout ok"
}
```

---

### POST /api/v1/auth/refresh
刷新 JWT Token，获取新的有效期。

**请求头**
```
Authorization: Bearer {access_token}
```

**响应** (200)
```json
{
  "success": true,
  "access_token": "new_token...",
  "token_type": "bearer"
}
```

---

## 用户路由 (前缀: /api/v1/users)

### GET /api/v1/users/me
获取当前登录用户的信息。

**请求头**
```
Authorization: Bearer {access_token}
```

**响应** (200)
```json
{
  "success": true,
  "user": {
    "id": 1,
    "username": "user@example.com",
    "created_at": "2024-01-01T12:00:00"
  }
}
```

---

### PUT /api/v1/users/me
更新当前用户的信息（用户名或密码）。

**请求头**
```
Authorization: Bearer {access_token}
```

**请求体**
```json
{
  "username": "newusername",
  "password": "newpassword"
}
```

**响应** (200)
```json
{
  "success": true,
  "message": "更新成功",
  "user": {
    "id": 1,
    "username": "newusername",
    "created_at": "2024-01-01T12:00:00"
  }
}
```

---

### GET /api/v1/users/images
获取当前用户的图片列表（分页）。

**请求头**
```
Authorization: Bearer {access_token}
```

**查询参数**
- `skip` (query, integer) - 分页偏移量，默认为 0
- `limit` (query, integer) - 每页数量，默认为 10

**响应** (200)
```json
{
  "success": true,
  "data": {
    "total": 25,
    "skip": 0,
    "limit": 10,
    "ids": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
  }
}
```

---

### GET /api/v1/users/multi-tasks
获取当前用户的多任务列表（分页）。

**请求头**
```
Authorization: Bearer {access_token}
```

**查询参数**
- `skip` (query, integer) - 分页偏移量，默认为 0
- `limit` (query, integer) - 每页数量，默认为 10

**响应** (200)
```json
{
  "success": true,
  "data": {
    "total": 5,
    "skip": 0,
    "limit": 10,
    "ids": [1, 2, 3, 4, 5]
  }
}
```

---

## 图片路由 (前缀: /api/v1/images)

### POST /api/v1/images/upload
上传图片文件。

**请求头**
```
Authorization: Bearer {access_token}
Content-Type: multipart/form-data
```

**请求参数**
- `image` (file) - 图片文件（必需）
- `user_id` (query) - 用户ID，默认为 1

**支持格式**
- .jpg, .jpeg, .png, .gif, .bmp, .webp, .tiff

**文件限制**
- 最大大小：10MB

**成功响应** (200)
```json
{
  "success": true,
  "imageId": 1,
  "filename": "photo_a1b2c3d4.jpg",
  "originalName": "photo.jpg",
  "fileSize": 250000
}
```

**失败响应** (200)
```json
{
  "success": false,
  "message": "不支持的文件类型。允许的类型: .jpg, .jpeg, .png, .gif, .bmp, .webp, .tiff"
}
```

---

### GET /api/v1/images/{image_id}
获取指定图片的文件。

**路径参数**
- `image_id` (path, integer) - 图片ID

**请求头**
```
Authorization: Bearer {access_token}
```

**响应** (200)
- 返回图片文件内容（二进制数据）

**错误响应**
- 404: 图片不存在或文件找不到

---

### POST /api/v1/images/{image_id}/ocr
对指定图片执行 OCR 识别（异步处理）。

**路径参数**
- `image_id` (path, integer) - 图片ID

**请求头**
```
Authorization: Bearer {access_token}
```

**响应** (200)
```json
{
  "success": true,
  "message": "图片 1 的OCR已添加到处理队列"
}
```

---

### GET /api/v1/images/{image_id}/ocr-results
获取指定图片的 OCR 结果列表（分页）。

**路径参数**
- `image_id` (path, integer) - 图片ID

**查询参数**
- `skip` (query, integer) - 分页偏移量，默认为 0
- `limit` (query, integer) - 每页数量，默认为 10

**请求头**
```
Authorization: Bearer {access_token}
```

**响应** (200)
```json
{
  "success": true,
  "data": {
    "total": 5,
    "skip": 0,
    "limit": 10,
    "ids": [1, 2, 3, 4, 5]
  }
}
```

---

## OCR 结果路由 (前缀: /api/v1/ocr-results)

### GET /api/v1/ocr-results/{ocr_id}
获取指定 OCR 结果的详细信息。

**路径参数**
- `ocr_id` (path, integer) - OCR 结果ID

**请求头**
```
Authorization: Bearer {access_token}
```

**响应** (200)
```json
{
  "success": true,
  "data": {
    "id": 1,
    "image_id": 1,
    "raw_text": "识别出的文本内容...",
    "status": "done",
    "created_at": "2024-01-01T12:00:00"
  }
}
```

**状态值**
- `pending` - 待处理
- `processing` - 处理中
- `done` - 完成
- `failed` - 失败

---

### GET /api/v1/ocr-results/{ocr_result_id}/structured-results
获取指定 OCR 结果的结构化结果列表（分页）。

**路径参数**
- `ocr_result_id` (path, integer) - OCR 结果ID

**查询参数**
- `skip` (query, integer) - 分页偏移量，默认为 0
- `limit` (query, integer) - 每页数量，默认为 10

**请求头**
```
Authorization: Bearer {access_token}
```

**响应** (200)
```json
{
  "success": true,
  "data": {
    "total": 3,
    "skip": 0,
    "limit": 10,
    "ids": [1, 2, 3]
  }
}
```

---

## 结构化结果路由 (前缀: /api/v1/structured-results)

### POST /api/v1/structured-results
对指定 OCR 结果进行结构化分析。

**请求头**
```
Authorization: Bearer {access_token}
```

**请求体**
```json
{
  "ocr_result_id": 1
}
```

**响应** (200)
```json
{
  "success": true,
  "message": "OcrResult 1 的结构化分析已添加到处理队列"
}
```

---

### GET /api/v1/structured-results/{structured_result_id}
获取指定结构化结果的详细信息。

**路径参数**
- `structured_result_id` (path, integer) - 结构化结果ID

**请求头**
```
Authorization: Bearer {access_token}
```

**响应** (200)
```json
{
  "success": true,
  "data": {
    "id": 1,
    "ocr_result_id": 1,
    "content": {
      "Time": "道光十二年二月初二日",
      "Time_AD": 1832,
      "Location": "小堤團虎禪垹輝訟",
      "Seller": "恆忠",
      "Buyer": "篋叙堂",
      "Middleman": "叔如玉",
      "Price": "感式捨榮串曹整",
      "Subject": "田肆點捌分玖厘",
      "Translation": "永久业产..."
    },
    "status": "done",
    "created_at": "2024-01-01T12:00:00"
  }
}
```

---

### GET /api/v1/structured-results/{structured_result_id}/relation-graphs
获取指定结构化结果的关系图列表（分页）。

**路径参数**
- `structured_result_id` (path, integer) - 结构化结果ID

**查询参数**
- `skip` (query, integer) - 分页偏移量，默认为 0
- `limit` (query, integer) - 每页数量，默认为 10

**请求头**
```
Authorization: Bearer {access_token}
```

**响应** (200)
```json
{
  "success": true,
  "data": {
    "total": 2,
    "skip": 0,
    "limit": 10,
    "ids": [1, 2]
  }
}
```

---

## 关系图路由 (前缀: /api/v1/relation-graphs)

### POST /api/v1/relation-graphs
对指定结构化结果进行关系图分析。

**请求头**
```
Authorization: Bearer {access_token}
```

**请求体**
```json
{
  "structured_result_id": 1
}
```

**响应** (200)
```json
{
  "success": true,
  "message": "StructuredResult 1 的关系图分析已添加到处理队列"
}
```

---

### GET /api/v1/relation-graphs/{relation_graph_id}
获取指定关系图的详细信息。

**路径参数**
- `relation_graph_id` (path, integer) - 关系图ID

**请求头**
```
Authorization: Bearer {access_token}
```

**响应** (200)
```json
{
  "success": true,
  "data": {
    "id": 1,
    "structured_result_id": 1,
    "content": {},
    "status": "done",
    "created_at": "2024-01-01T12:00:00"
  }
}
```

---

## 多任务路由 (前缀: /api/v1/multi-tasks)

### POST /api/v1/multi-tasks
创建跨文档分析任务。

**请求头**
```
Authorization: Bearer {access_token}
```

**请求体**
```json
{
  "structured_result_ids": [1, 2, 3]
}
```

**响应** (200)
```json
{
  "success": true,
  "message": "多任务创建成功",
  "multi_task_id": 1,
  "structured_result_ids": [1, 2, 3],
  "created_at": "2024-01-01T12:00:00"
}
```

---

### GET /api/v1/multi-tasks/{multi_task_id}
获取指定多任务的详细信息。

**路径参数**
- `multi_task_id` (path, integer) - 多任务ID

**请求头**
```
Authorization: Bearer {access_token}
```

**响应** (200)
```json
{
  "success": true,
  "data": {
    "id": 1,
    "user_id": 1,
    "status": "done",
    "structured_result_ids": [1, 2, 3],
    "created_at": "2024-01-01T12:00:00"
  }
}
```

---

### GET /api/v1/multi-tasks/{multi_task_id}/multi-relation-graphs
获取指定多任务的跨文档关系图列表（分页）。

**路径参数**
- `multi_task_id` (path, integer) - 多任务ID

**查询参数**
- `skip` (query, integer) - 分页偏移量，默认为 0
- `limit` (query, integer) - 每页数量，默认为 10

**请求头**
```
Authorization: Bearer {access_token}
```

**响应** (200)
```json
{
  "success": true,
  "data": {
    "total": 1,
    "skip": 0,
    "limit": 10,
    "ids": [1]
  }
}
```

---

## 跨文档关系图路由 (前缀: /api/v1/multi-relation-graphs)

### POST /api/v1/multi-relation-graphs
对指定多任务进行跨文档分析。

**请求头**
```
Authorization: Bearer {access_token}
```

**请求体**
```json
{
  "multi_task_id": 1
}
```

**响应** (200)
```json
{
  "success": true,
  "message": "MultiTask 1 的跨文档分析已添加到处理队列"
}
```

---

### GET /api/v1/multi-relation-graphs/{multi_relation_graph_id}
获取指定跨文档关系图的详细信息。

**路径参数**
- `multi_relation_graph_id` (path, integer) - 跨文档关系图ID

**请求头**
```
Authorization: Bearer {access_token}
```

**响应** (200)
```json
{
  "success": true,
  "data": {
    "id": 1,
    "multi_task_id": 1,
    "content": {},
    "status": "done",
    "created_at": "2024-01-01T12:00:00"
  }
}
```

---

## 使用流程

### 完整的端到端工作流程

#### 1. 初始设置（首次使用）
```
POST /api/v1/auth/register  -> 注册账户，获得用户ID
POST /api/v1/auth/login     -> 登录，获得 access_token
```

#### 2. 图片处理流程
```
POST /api/v1/images/upload              -> 上传图片，获得 imageId
POST /api/v1/images/{imageId}/ocr       -> 触发 OCR 识别
GET  /api/v1/images/{imageId}/ocr-results  -> 获取 OCR 结果列表
GET  /api/v1/ocr-results/{ocrId}        -> 获取单个 OCR 结果详情
```

#### 3. 结构化分析流程
```
POST /api/v1/structured-results                     -> 创建结构化分析任务
GET  /api/v1/structured-results/{structuredId}      -> 获取结构化结果详情
POST /api/v1/relation-graphs                        -> 创建关系图分析任务
GET  /api/v1/relation-graphs/{relationGraphId}      -> 获取关系图详情
```

#### 4. 跨文档分析流程
```
POST /api/v1/multi-tasks                            -> 创建跨文档任务
POST /api/v1/multi-relation-graphs                  -> 创建跨文档分析任务
GET  /api/v1/multi-relation-graphs/{multiGraphId}   -> 获取跨文档分析结果
```

---

## 错误处理

所有 API 错误响应遵循以下格式：

**错误响应示例**
```json
{
  "detail": "错误信息描述"
}
```

**HTTP 状态码**
- `200` - 请求成功
- `400` - 请求参数错误或业务逻辑失败
- `401` - 认证失败或 Token 无效/过期
- `404` - 资源不存在
- `500` - 服务器错误

---

## 速率限制

目前无速率限制

---

## 版本历史

- **v1.0** - 初始版本，包括用户认证、图片管理、OCR、结构化分析和跨文档分析功能
**请求**
```
GET /api
```

**响应**
```json
"Hello, World!"
```

---

### 2. 注册
**请求**
```
POST /register
```

**请求体**
```json
{
  "username": "user@example.com",
  "password": "password123"
}
```

**响应** (成功)
```json
{
  "success": true,
  "message": "注册成功",
  "userId": 1,
  "username": "user@example.com"
}
```

**响应** (失败)
```json
{
  "detail": "用户名已存在"
}
```

---

### 3. 登录
**请求**
```
POST /login
```

**请求体**
```json
{
  "username": "user@example.com",
  "password": "password123"
}
```

**响应** (成功)
```json
{
  "success": true,
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": 1,
  "username": "user@example.com"
}
```

**错误**
- 401: 用户名或密码错误

---

### 4. 获取用户信息
**请求**
```
GET /user/info
```

**请求头**
- Authorization: `Bearer {access_token}`

**响应** (成功)
```json
{
  "success": true,
  "user": {
    "id": 1,
    "username": "user@example.com",
    "created_at": "2024-01-01T12:00:00"
  }
}
```

**错误**
- 401: Token无效或过期
- 404: 用户不存在

---

### 5. 登出
**请求**
```
POST /logout
```

**请求头**
- Authorization: `Bearer {access_token}`

**响应** (成功)
```json
{
  "success": true,
  "message": "logout ok"
}
```

**错误**
- 401: Token无效或过期

---

### 6. 上传图片
**请求**
```
POST /api/upload
```

**请求头**
- Authorization: `Bearer {access_token}`
- Content-Type: `multipart/form-data`

**请求参数**
- `image` (file) - 图片文件（必需）
- `user_id` (query) - 用户ID，默认为1

**支持格式**
- .jpg, .jpeg, .png, .gif, .bmp, .webp, .tiff

**文件限制**
- 最大大小：10MB

**响应** (成功)
```json
{
  "success": true,
  "imageId": 1,
  "filename": "photo_a1b2c3d4.jpg",
  "originalName": "photo.jpg",
  "fileSize": 250000
}
```

**响应** (失败)
```json
{
  "success": false,
  "message": "错误信息"
}
```

**常见错误**
- 不支持的文件类型
- 文件过大
- 文件为空
- 保存文件失败

---

### 7. 获取图片
**请求**
```
GET /api/pic/{id}
```

**请求头**
- Authorization: `Bearer {access_token}`

**参数**
- `id` (path) - 图片ID

**响应**
- 返回图片文件内容（二进制数据）

**错误**
- 401: Token无效或过期
- 404: 图片不存在

---

### 8. 获取分析结果
**请求**
```
GET /api/analysis/{id}
```

**请求头**
- Authorization: `Bearer {access_token}`

**参数**
- `id` (path) - 分析ID

**响应**
```json
{
  "nodes": [
    {
      "id": "1",
      "name": "劉永濟",
      "type": "person",
      "category": "立約人",
      "symbolSize": 40,
      "itemStyle": {
        "color": "#5470c6",
        "borderColor": "#fff",
        "borderWidth": 2,
        "shadowBlur": 10,
        "shadowColor": "rgba(0, 0, 0, 0.3)"
      }
    }
  ],
  "links": [
    {
      "source": "1",
      "target": "file2_node1",
      "value": "出让",
      "lineStyle": {
        "color": "#ff0000",
        "width": 2
      }
    }
  ],
  "categories": [
    {"name": "立約人"},
    {"name": "标的"}
  ],
  "txt": "ID: 1 的识别结果"
}
```

---

### 9. 获取OCR结果
**请求**
```
GET /api/ocr/{id}
```

**请求头**
- Authorization: `Bearer {access_token}`

**参数**
- `id` (path) - OCR结果ID

**响应** (成功)
```json
{
  "success": true,
  "data": {
    "id": 1,
    "image_id": 1,
    "raw_text": "识别出的文本内容",
    "created_at": "2024-01-01T12:00:00"
  }
}
```

**错误**
- 401: Token无效或过期
- 404: OCR结果不存在

---

### 10. 获取用户的图片列表
**请求**
```
GET /api/user-images
```

**请求头**
- Authorization: `Bearer {access_token}`

**查询参数**
- `user_id` (query) - 用户ID（必需）
- `skip` (query) - 分页偏移量，默认为0
- `limit` (query) - 每页数量，默认为10

**响应** (成功)
```json
{
  "success": true,
  "data": {
    "total": 25,
    "skip": 0,
    "limit": 10,
    "ids": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
  }
}
```

**错误**
- 401: Token无效或过期
- 404: 用户不存在

---

### 11. 获取图片的OCR结果列表
**请求**
```
GET /api/ocr-results/{image_id}
```

**请求头**
- Authorization: `Bearer {access_token}`

**路径参数**
- `image_id` (path) - 图片ID（必需）

**查询参数**
- `skip` (query) - 分页偏移量，默认为0
- `limit` (query) - 每页数量，默认为10

**响应** (成功)
```json
{
  "success": true,
  "data": {
    "total": 5,
    "skip": 0,
    "limit": 10,
    "ids": [1, 2, 3, 4, 5]
  }
}
```

**错误**
- 401: Token无效或过期
- 404: 图片不存在

---

## 认证说明

所有API端点（除了 `/register` 和 `/login`）都需要在请求头中带上有效的JWT token：

```
Authorization: Bearer {access_token}
```

Token通过登录接口获得，有效期为24小时。

## 使用流程

### 第一次使用：
1. **注册账户** -> `POST /register` -> 获得用户ID
2. **登录** -> `POST /login` -> 获得 `access_token`
3. **上传图片** -> `POST /api/upload` -> 获得 `imageId`

### 后续使用：
1. **登录** -> `POST /login` -> 获得 `access_token`
2. **获取用户图片列表** -> `GET /api/images?user_id={user_id}` -> 获得图片ID列表
3. **获取图片的OCR结果列表** -> `GET /api/ocr-results/{image_id}` -> 获得OCR结果ID列表
4. **获取单个OCR结果** -> `GET /api/ocr/{ocr_result_id}` -> 获得OCR结果详情
5. **获取原始图片** -> `GET /api/pic/{image_id}` -> 获得原始图片
