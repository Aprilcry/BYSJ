from flask import Blueprint, request, jsonify, Response
from flask_login import login_required, current_user
import requests
import json
import time

from app.models import UserIngredient

# 智谱AI API配置
API_KEY = "1c0afcaadb624b349a1d9a8533f6127c.LYaS9fY6nX5zOXMi"
API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

# 创建蓝图
bp = Blueprint('ai', __name__, url_prefix='/api/ai')

# 获取用户的食材列表
@bp.route('/ingredients', methods=['GET'])
@login_required
def get_ingredients():
    try:
        print(f"[调试] 获取用户 {current_user.id} 的食材列表")
        # 查询用户的食材
        user_ingredients = UserIngredient.query.filter_by(user_id=current_user.id).all()
        print(f"[调试] 找到 {len(user_ingredients)} 个食材")
        
        # 获取食材名称
        ingredients = []
        for user_ingredient in user_ingredients:
            if user_ingredient.ingredient:
                ingredients.append(user_ingredient.ingredient.name)
                print(f"[调试] 食材: {user_ingredient.ingredient.name}")
        
        print(f"[调试] 食材列表: {ingredients}")
        
        return jsonify({
            'success': True,
            'ingredients': ingredients
        })
    except Exception as e:
        print(f"[调试] 获取食材失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# 处理AI聊天请求（流式）
@bp.route('/chat', methods=['POST'])
def chat():
    try:
        # 获取请求数据
        data = request.get_json()
        print(f"[调试] 接收到的请求数据: {data}")
        message = data.get('message', '')
        
        if not message:
            print("[调试] 消息为空")
            return jsonify({
                'success': False,
                'error': '消息不能为空'
            }), 400
        
        print(f"[调试] 收到AI请求: {message}")
        
        # 构建请求参数
        payload = {
            "model": "glm-4.7-flash",
            "messages": [
                {
                    "role": "system",
                    "content": "你是一位专业的厨艺专家助手，精通各种菜谱和烹饪技巧。请以友好、专业的语气回答用户的问题，回答可以尽量简短。"
                },
                {
                    "role": "user",
                    "content": message
                }
            ],
            "max_tokens": 1024,
            "temperature": 0.7,
            "stream": True,  # 启用流式输出
            "thinking": {
                "type": "disabled"  # 禁用深度思考，减少tokens使用
            }
        }
        
        print(f"[调试] 请求参数: {json.dumps(payload, ensure_ascii=False)}")
        
        # 发送请求到智谱AI
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }
        
        print("[调试] 发送请求到智谱AI...")
        print(f"[调试] API URL: {API_URL}")
        print(f"[调试] Headers: {headers}")
        
        # 增加超时设置
        response = requests.post(
            API_URL, 
            headers=headers, 
            data=json.dumps(payload), 
            stream=True,
            timeout=30  # 设置30秒超时
        )
        
        print(f"[调试] 响应状态码: {response.status_code}")
        print(f"[调试] 响应头: {dict(response.headers)}")
        
        # 检查请求是否成功
        try:
            response.raise_for_status()
            print("[调试] 请求成功")
        except requests.exceptions.HTTPError as e:
            print(f"[调试] HTTP错误: {str(e)}")
            print(f"[调试] 响应内容: {response.text}")
            raise
        
        print("[调试] 开始流式处理响应...")
        
        # 流式处理响应
        def generate():
            try:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        # 处理每个chunk
                        chunk_str = chunk.decode('utf-8')
                        print(f"[调试] 收到chunk: {chunk_str}")
                        # 分割SSE格式的响应
                        lines = chunk_str.split('\n')
                        for line in lines:
                            line = line.strip()
                            if line.startswith('data: '):
                                data_part = line[6:]
                                if data_part == '[DONE]':
                                    print("[调试] 响应结束")
                                    yield f"data: {{\"done\": true}}\n\n"
                                else:
                                    try:
                                        chunk_data = json.loads(data_part)
                                        print(f"[调试] 解析的chunk数据: {chunk_data}")
                                        if 'choices' in chunk_data and chunk_data['choices']:
                                            delta = chunk_data['choices'][0].get('delta', {})
                                            if 'content' in delta:
                                                # 处理内容中的特殊字符
                                                content = delta['content'].replace('\n', '\\n').replace('"', '\\"')
                                                print(f"[调试] 生成内容: {content}")
                                                yield f"data: {{\"content\": \"{content}\"}}\n\n"
                                            # 处理思考内容
                                            if 'reasoning_content' in delta:
                                                # 可以选择是否传递思考内容
                                                reasoning_content = delta['reasoning_content'].replace('\n', '\\n').replace('"', '\\"')
                                                print(f"[调试] 生成思考内容: {reasoning_content}")
                                                # yield f"data: {{\"reasoning_content\": \"{reasoning_content}\"}}\n\n"
                                    except json.JSONDecodeError as e:
                                        print(f"[调试] JSON解析错误: {str(e)}")
                                        print(f"[调试] 错误数据: {data_part}")
                                        pass
            except Exception as e:
                print(f"[调试] 生成响应时出错: {str(e)}")
                import traceback
                traceback.print_exc()
        
        return Response(generate(), mimetype='text/event-stream')
        
    except requests.exceptions.RequestException as e:
        print(f"[调试] AI请求失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'AI服务暂时不可用，请稍后再试'
        }), 500
    except Exception as e:
        print(f"[调试] 聊天处理失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
