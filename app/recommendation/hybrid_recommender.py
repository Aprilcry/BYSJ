import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from app.models import Recipe, UserIngredient, RecipeIngredient, User, PostLike, Favorite, Comment, RecipeView
from app import db

class HybridRecommender:
    def __init__(self):
        self.cf_similarity_matrix = None
        self.content_similarity_matrix = None
        self.recipe_ids = []
        self.recipe_features = []
        self.interaction_matrix = None
        self.user_ids = []
    
    def prepare_data(self):
        """准备推荐所需的数据"""
        try:
            print("开始准备数据...")
            # 获取所有菜谱
            recipes = Recipe.query.all()
            print(f"获取到 {len(recipes)} 个菜谱")
            self.recipe_ids = [recipe.id for recipe in recipes]
            
            # 构建用户-菜谱交互矩阵
            print("构建用户-菜谱交互矩阵...")
            self._build_interaction_matrix()
            
            # 提取菜谱特征
            print("提取菜谱特征...")
            self._extract_recipe_features(recipes)
            print("数据准备完成！")
        except Exception as e:
            print(f"数据准备失败: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _build_interaction_matrix(self):
        """构建用户-菜谱交互矩阵"""
        try:
            # 获取所有用户
            users = User.query.all()
            print(f"获取到 {len(users)} 个用户")
            self.user_ids = [user.id for user in users]
            
            # 初始化交互矩阵
            num_users = len(self.user_ids)
            num_recipes = len(self.recipe_ids)
            print(f"初始化交互矩阵: {num_users} x {num_recipes}")
            self.interaction_matrix = np.zeros((num_users, num_recipes))
            
            # 映射用户ID和菜谱ID到矩阵索引
            user_id_to_idx = {user_id: idx for idx, user_id in enumerate(self.user_ids)}
            recipe_id_to_idx = {recipe_id: idx for idx, recipe_id in enumerate(self.recipe_ids)}
            
            # 填充交互矩阵
            # 1. 浏览记录
            views = RecipeView.query.all()
            print(f"处理 {len(views)} 条浏览记录")
            for view in views:
                if view.user_id in user_id_to_idx and view.recipe_id in recipe_id_to_idx:
                    user_idx = user_id_to_idx[view.user_id]
                    recipe_idx = recipe_id_to_idx[view.recipe_id]
                    self.interaction_matrix[user_idx, recipe_idx] += 1
            
            # 2. 收藏
            favorites = Favorite.query.filter_by(target_type='recipe').all()
            print(f"处理 {len(favorites)} 条收藏记录")
            for favorite in favorites:
                if favorite.user_id in user_id_to_idx and favorite.target_id in recipe_id_to_idx:
                    user_idx = user_id_to_idx[favorite.user_id]
                    recipe_idx = recipe_id_to_idx[favorite.target_id]
                    self.interaction_matrix[user_idx, recipe_idx] += 3
            
            # 3. 点赞（暂时不处理，因为PostLike只用于帖子）
            # 4. 评论（暂时不处理，因为Comment只用于帖子）
            print("交互矩阵构建完成！")
        except Exception as e:
            print(f"构建交互矩阵失败: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _extract_recipe_features(self, recipes):
        """提取菜谱特征"""
        try:
            # 收集所有可能的特征
            all_ingredients = set()
            all_categories = set()
            all_difficulties = set()
            all_tastes = set()
            
            # 收集特征
            print("收集菜谱特征...")
            for recipe in recipes:
                all_categories.add(recipe.category)
                all_difficulties.add(recipe.difficulty)
                all_tastes.add(recipe.taste)
                # 收集食材
                for ri in recipe.ingredients:
                    all_ingredients.add(ri.ingredient.name)
            
            print(f"收集到 {len(all_ingredients)} 种食材, {len(all_categories)} 个菜系, {len(all_difficulties)} 个难度, {len(all_tastes)} 种口味")
            
            # 特征映射
            ingredient_to_idx = {ingredient: idx for idx, ingredient in enumerate(all_ingredients)}
            category_to_idx = {category: idx for idx, category in enumerate(all_categories)}
            difficulty_to_idx = {difficulty: idx for idx, difficulty in enumerate(all_difficulties)}
            taste_to_idx = {taste: idx for idx, taste in enumerate(all_tastes)}
            
            # 构建特征向量
            print("构建特征向量...")
            for recipe in recipes:
                # 初始化特征向量
                feature_vector = []
                
                # 食材特征（one-hot）
                ingredient_features = [0] * len(all_ingredients)
                for ri in recipe.ingredients:
                    if ri.ingredient.name in ingredient_to_idx:
                        ingredient_features[ingredient_to_idx[ri.ingredient.name]] = 1
                feature_vector.extend(ingredient_features)
                
                # 菜系特征（one-hot）
                category_features = [0] * len(all_categories)
                if recipe.category in category_to_idx:
                    category_features[category_to_idx[recipe.category]] = 1
                feature_vector.extend(category_features)
                
                # 难度特征（one-hot）
                difficulty_features = [0] * len(all_difficulties)
                if recipe.difficulty in difficulty_to_idx:
                    difficulty_features[difficulty_to_idx[recipe.difficulty]] = 1
                feature_vector.extend(difficulty_features)
                
                # 口味特征（one-hot）
                taste_features = [0] * len(all_tastes)
                if recipe.taste in taste_to_idx:
                    taste_features[taste_to_idx[recipe.taste]] = 1
                feature_vector.extend(taste_features)
                
                # 烹饪时间特征（归一化）
                cook_time = recipe.cook_time / 120.0  # 假设最长烹饪时间为120分钟
                feature_vector.append(cook_time)
                
                # 准备时间特征（归一化）
                prep_time = recipe.prep_time / 60.0  # 假设最长准备时间为60分钟
                feature_vector.append(prep_time)
                
                self.recipe_features.append(feature_vector)
            
            # 转换为numpy数组
            self.recipe_features = np.array(self.recipe_features)
            print(f"特征向量构建完成，形状: {self.recipe_features.shape}")
        except Exception as e:
            print(f"提取菜谱特征失败: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def calculate_similarity_matrices(self):
        """计算相似度矩阵"""
        try:
            # 计算协同过滤相似度矩阵
            if self.interaction_matrix is not None:
                print("计算协同过滤相似度矩阵...")
                self.cf_similarity_matrix = cosine_similarity(self.interaction_matrix.T)
                print(f"协同过滤相似度矩阵形状: {self.cf_similarity_matrix.shape}")
            else:
                print("交互矩阵为空，跳过协同过滤相似度计算")
            
            # 计算内容相似度矩阵
            if len(self.recipe_features) > 0:
                print("计算内容相似度矩阵...")
                self.content_similarity_matrix = cosine_similarity(self.recipe_features)
                print(f"内容相似度矩阵形状: {self.content_similarity_matrix.shape}")
            else:
                print("特征向量为空，跳过内容相似度计算")
            print("相似度矩阵计算完成！")
        except Exception as e:
            print(f"计算相似度矩阵失败: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def get_recommendations(self, target_recipe_id, top_n=5, weight_cf=0.6, weight_content=0.4):
        """获取混合推荐结果"""
        try:
            if target_recipe_id not in self.recipe_ids:
                print(f"菜谱ID {target_recipe_id} 不在菜谱列表中")
                return []
            
            # 获取目标菜谱的索引
            target_idx = self.recipe_ids.index(target_recipe_id)
            
            # 计算协同过滤得分
            if self.cf_similarity_matrix is not None:
                cf_scores = self.cf_similarity_matrix[target_idx]
            else:
                cf_scores = np.zeros(len(self.recipe_ids))
            
            # 计算内容-based得分
            if self.content_similarity_matrix is not None:
                content_scores = self.content_similarity_matrix[target_idx]
            else:
                content_scores = np.zeros(len(self.recipe_ids))
            
            # 加权融合
            final_scores = weight_cf * cf_scores + weight_content * content_scores
            
            # 排除目标菜谱本身
            final_scores[target_idx] = -1
            
            # 排序并获取Top-N
            top_indices = np.argsort(final_scores)[::-1][:top_n]
            
            # 转换为菜谱ID
            recommended_recipe_ids = [self.recipe_ids[idx] for idx in top_indices]
            
            # 获取菜谱详情
            recommended_recipes = []
            for recipe_id in recommended_recipe_ids:
                recipe = Recipe.query.get(recipe_id)
                if recipe:
                    recommended_recipes.append(recipe)
            
            print(f"为菜谱ID {target_recipe_id} 生成了 {len(recommended_recipes)} 个推荐")
            return recommended_recipes
        except Exception as e:
            print(f"获取推荐失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

# 全局推荐器实例
recommender = HybridRecommender()

# 初始化推荐器
def init_recommender():
    """初始化推荐器"""
    try:
        print("正在初始化推荐器...")
        recommender.prepare_data()
        recommender.calculate_similarity_matrices()
        print("推荐器初始化完成！")
    except Exception as e:
        print(f"初始化推荐器失败: {str(e)}")
        import traceback
        traceback.print_exc()
