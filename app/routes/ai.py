from flask import Blueprint, request, jsonify, Response
from flask_login import login_required, current_user
import requests
import json
import time

from app.models import UserIngredient

# DeepSeek API配置
API_KEY = "sk-3873bc920ee547418eeb0dcef8d8e254"
API_URL = "https://api.deepseek.com/chat/completions"

# 创建蓝图
bp = Blueprint('ai', __name__, url_prefix='/api/ai')

# 获取用户的食材列表
@bp.route('/ingredients', methods=['GET'])
@login_required
def get_ingredients():
    try:
        # 查询用户的食材
        user_ingredients = UserIngredient.query.filter_by(user_id=current_user.id).all()
        
        # 获取食材名称
        ingredients = []
        for user_ingredient in user_ingredients:
            if user_ingredient.ingredient:
                ingredients.append(user_ingredient.ingredient.name)
        
        return jsonify({
            'success': True,
            'ingredients': ingredients
        })
    except Exception as e:
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
        message = data.get('message', '')
        
        if not message:
            return jsonify({
                'success': False,
                'error': '消息不能为空'
            }), 400
        
        # 构建请求参数
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": '''
                                你是一位专业的家庭厨艺助手，精通中餐家常菜的制作方法和烹饪技巧。
                                请严格遵守以下规则回答用户的问题：
                                1.  所有回答必须基于用户当前拥有的食材，不要推荐用户没有的食材
                                2.  回答要简洁实用，步骤清晰，避免使用过于专业的术语
                                3.  优先推荐制作简单、耗时短的家常菜
                                4.  如果用户的问题与烹饪无关，请礼貌地说明你只能回答厨艺相关问题
                                5.  对于不确定的内容，不要编造，如实告知用户即可
                                '''
                },
                {
                    "role": "user",
                    "content": message
                }
            ],
            "max_tokens": 4096,
            "temperature": 0.7,
            "stream": True  # 启用流式输出
        }
        
        # 发送请求到DeepSeek API
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }
        
        # 增加超时设置
        response = requests.post(
            API_URL, 
            headers=headers, 
            data=json.dumps(payload), 
            stream=True,
            timeout=30  # 设置30秒超时
        )
        
        # 检查请求是否成功
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise
        
        # 流式处理响应
        def generate():
            try:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        # 处理每个chunk
                        chunk_str = chunk.decode('utf-8')
                        # 分割SSE格式的响应
                        lines = chunk_str.split('\n')
                        for line in lines:
                            line = line.strip()
                            if line.startswith('data: '):
                                data_part = line[6:]
                                if data_part == '[DONE]':
                                    yield f"data: {{\"done\": true}}\n\n"
                                else:
                                    try:
                                        chunk_data = json.loads(data_part)
                                        if 'choices' in chunk_data and chunk_data['choices']:
                                            delta = chunk_data['choices'][0].get('delta', {})
                                            if 'content' in delta:
                                                # 处理内容中的特殊字符
                                                content = delta['content'].replace('\n', '\\n').replace('"', '\\"')
                                                # 构造响应字符串
                                                response_str = f'data: {{"choices": [{{"delta": {{"content": "{content}"}}}}]}}\n\n'
                                                yield response_str
                                    except json.JSONDecodeError:
                                        pass
            except Exception as e:
                import traceback
                traceback.print_exc()
        
        return Response(generate(), mimetype='text/event-stream')
        
    except requests.exceptions.RequestException as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'AI服务暂时不可用，请稍后再试'
        }), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
