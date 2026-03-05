## Python

`python 3.12.9`

## 安装依赖

```bash
pip install -r requirements.txt
```

## 启动服务器

```bash
uvicorn main:app
```

开发用 - 启动服务器并开启热重载：

```bash
uvicorn main:app -reload
```

## API测试

依赖：

```bash
pip install pytest
```

运行：

```bash
pytest api_test/test_api.py -v -s
```
