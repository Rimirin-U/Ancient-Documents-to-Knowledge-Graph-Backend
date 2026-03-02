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

### 2. 上传图片
**请求**
```
POST /api/upload
```

**请求体**
- Content-Type: `multipart/form-data`
- 参数: `image` (file) - 图片文件

**响应** (成功)
```json
{
  "success": true,
  "analysisId": "1704067800123"
}
```

**响应** (失败)
```json
{
  "success": false,
  "message": "错误信息"
}
```

---

### 3. 获取图片
**请求**
```
GET /api/pic/{id}
```

**参数**
- `id` (path) - 分析ID（analysisId）

**响应**
- 返回图片文件

**错误**
- 404: 图片不存在

---

### 4. 获取分析结果
**请求**
```
GET /api/analysis/{id}
```

**参数**
- `id` (path) - 分析ID（analysisId）

**响应**
```json
{
  "nodes": [
    {
      "id": "1704067800123",
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
      "source": "1704067800123",
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
  "txt": "ID: 1704067800123 的识别结果"
}
```

---

## 使用流程

1. **上传图片** -> `POST /api/upload` -> 获得 `analysisId`
2. **获取分析** -> `GET /api/analysis/{analysisId}` -> 获得分析结果
3. **获取图片** -> `GET /api/pic/{analysisId}` -> 获得原始图片
