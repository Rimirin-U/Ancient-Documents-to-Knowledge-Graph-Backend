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

```bash
python api_test/test_api.py
```