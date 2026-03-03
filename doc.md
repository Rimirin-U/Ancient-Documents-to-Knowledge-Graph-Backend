# API 文档

## 基础信息
- 基地址: `http://localhost:3000`
- 所有请求和响应均为 JSON 格式

---

## API 端点

### 1. 测试
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
