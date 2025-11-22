import os
import json
import time # 增加延遲，避免 API 速率限制
from openai import OpenAI

# --- 1. 設定與初始化 ---
# 警告：請確保您的 API Key 已經設置為環境變數 OPENAI_API_KEY
API_KEY = os.environ.get("OPENAI_API_KEY")
if not API_KEY:
    print("錯誤：請設置 OPENAI_API_KEY 環境變數。")
    exit()

client = OpenAI(api_key=API_KEY)

# 檔案路徑設定
STATE_FILE = "lab2_output/state/save_1.json"
REVIEW_FILE = "lab2_output/summary_1.txt"
os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True) # 確保資料夾存在

DEFAULT_STATE = {
    "player": {
        "gold": 100,
        "reputation_level": "Apprentice",
        "days_passed": 0
    },
    "inventory": {
        "ingredients": {
            "Water": 10,
            "Basic Herb": 5
        },
        "potions": {}
    },
    "current_quest": {},
    "game_log": [] # 記錄所有重要回合的 LLM 輸入/輸出
}

# --- 2. 狀態與日誌管理函式 ---

def load_state():
    """載入遊戲狀態，如果檔案不存在則返回 DEFAULT_STATE。"""
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_STATE.copy()

def save_state(state):
    """儲存當前遊戲狀態到 JSON 檔案。"""
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=4, ensure_ascii=False)

def update_state(state, updates):
    """根據 LLM 輸出更新遊戲狀態的通用函式。"""
    if updates.get('gold_change'):
        state['player']['gold'] += updates['gold_change']
    if updates.get('reputation_change'):
        # 這裡需要實作複雜的聲望等級邏輯
        # 簡單範例：state['player']['reputation_level'] = updates['reputation_change']
        pass 
    if updates.get('inventory_updates'):
        for item, count in updates['inventory_updates'].items():
            state['inventory']['ingredients'][item] = state['inventory']['ingredients'].get(item, 0) + count
    # 其他更新...
    return state


def call_llm_json(user_prompt, system_message, log_name):
    """呼叫 LLM 並強制要求 JSON 格式輸出。"""
    print(f"\n--- 執行 LLM 任務: {log_name} ---")
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", # 建議使用 gpt-4 或 gpt-4o 家族以獲得更好的遵循指示能力
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"} # 強制 JSON 輸出
        )
        
        response_text = response.choices[0].message.content.strip()
        json_output = json.loads(response_text)
        
        # 記錄到 game_log
        current_state = load_state()
        current_state["game_log"].append({
            "task": log_name,
            "user_prompt": user_prompt,
            "llm_output": json_output,
            "day": current_state["player"]["days_passed"]
        })
        save_state(current_state)

        return json_output

    except Exception as e:
        print(f"❌ LLM 呼叫失敗或 JSON 解析錯誤: {e}")
        return None

# --- 3. 核心 LLM 任務函式 ---

def task_1_quest_generation(state):
    """任務 1: 根據聲望生成新任務 (JSON 輸出)。"""
    
    system_msg = "你是一個 NPC 客戶。請生成一個符合當前聲望的任務。"
    user_prompt = f"""
    我的聲望等級是 {state['player']['reputation_level']}。請生成一個新任務。
    回覆必須是 JSON 格式：{{ "name": "...", "potion_name": "...", "reward": 0 }}
    """
    
    result = call_llm_json(user_prompt, system_msg, "Quest_Generation")
    if result:
        state['current_quest'] = result
        print(f"✅ 新任務生成：{result['name']}")
    return state

def task_2_recipe_digest(state):
    """任務 2: 配方分析與消化輸出 (關鍵的思維鏈步驟)。"""
    
    # --- ⚠️ 這是您必須仔細填寫和調整的環節 ⚠️ ---
    # 這是作業的核心：讓 LLM 比較兩組數據 (配方 vs. 庫存)
    
    inventory_json = json.dumps(state['inventory']['ingredients'])
    quest_name = state['current_quest']['potion_name']

    system_msg = """
    你是一位資深煉金術士助手。你的任務是執行兩階段分析：
    1. 根據藥劑名稱，確定所需的完整材料清單。
    2. 參考提供的庫存，列出**所有不足**的材料及數量。
    請以嚴格的 JSON 格式回覆：{ "required_ingredients": {"材料A": N, ...}, "missing_ingredients": {"材料B": X, ...}, "narrative": "..." }
    """
    user_prompt = f"""
    當前任務藥劑：{quest_name}
    當前庫存：{inventory_json}
    請執行分析並回覆。
    """
    
    result = call_llm_json(user_prompt, system_msg, "Recipe_Digest")
    
    if result and result.get('missing_ingredients'):
        print(f"🔎 消化結果：缺少以下材料：{result['missing_ingredients']}")
        # 將缺少的材料清單儲存到 state 中，以便在任務 3 中引導玩家
        state['current_quest']['missing'] = result['missing_ingredients']
    return state

def task_3_action_evaluation(state, player_action):
    """任務 3: 根據玩家行動評估結果並更新狀態 (JSON 輸出)。"""
    
    # --- ⚠️ 請確保此處的提示能引導 LLM 正確地進行敘事和數值更新 ⚠️ ---
    
    missing_items = json.dumps(state['current_quest'].get('missing', {}))
    
    system_msg = "你是一位說書人，請根據玩家的行動和目標，生成一個簡短的冒險敘事，並輸出結構化的狀態變化。"
    user_prompt = f"""
    玩家行動：{player_action}
    玩家目標（缺少的材料）：{missing_items}
    玩家目前金幣：{state['player']['gold']}
    請以 JSON 格式回覆：{{ "narrative": "...", "gold_change": -10, "inventory_updates": {{"材料名": 1}} }}
    """
    
    result = call_llm_json(user_prompt, system_msg, "Action_Evaluation")
    
    if result:
        print(f"📖 冒險日誌：{result.get('narrative', '...')}。")
        state = update_state(state, result)
        
    return state

def task_4_transaction_update(state):
    """任務 4: 交付任務，更新聲望和金幣。"""
    
    # --- ⚠️ 請確保此處的提示能引導 LLM 執行最終交易邏輯 ⚠️ ---
    
    system_msg = "你是一位公正的客戶，請敘述任務交付結果，並以 JSON 格式輸出金幣和聲望的最終變動。"
    user_prompt = f"""
    玩家交付了 {state['current_quest']['potion_name']}。
    原始任務回報是 {state['current_quest']['reward']}。
    請敘述客戶的反應，並回覆：{{ "narrative": "...", "gold_change": 80, "reputation_change": "+10" }}
    """
    
    result = call_llm_json(user_prompt, system_msg, "Transaction_Update")
    
    if result:
        print(f"💰 交易完成：{result.get('narrative', '...')}")
        state = update_state(state, result)
        
    return state

def task_5_final_review(game_log):
    """任務 5: 根據整個遊戲日誌生成可享樂的評論。"""
    
    # --- ⚠️ 這是作業的第二個核心：撰寫一份生動且滿足所有要求的評論提示 ⚠️ ---
    
    log_summary = json.dumps(game_log, indent=2, ensure_ascii=False)
    
    system_msg = """
    你是一位鎮上無所不知、愛管閒事的八卦記者。
    請分析提供的遊戲日誌。你的報導必須是五段式，語氣風趣、充滿暗示和誇大。
    請在報導結尾給予一個 Witty Score (S/A/B/C/D/F) 級別的評價。
    請以純文本格式回覆，不要使用 JSON。
    """
    user_prompt = f"請根據以下完整的遊戲日誌，撰寫一篇生動的八卦報導：\n\n{log_summary}"

    print("\n--- 執行 LLM 任務: Final_Review ---")
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", # 建議使用更高階模型來寫作長篇敘事
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_prompt}
            ]
        )
        review_text = response.choices[0].message.content.strip()
        
        with open(REVIEW_FILE, 'w', encoding='utf-8') as f:
            f.write(review_text)
        print(f"✅ 遊戲評論已生成並儲存到 {REVIEW_FILE}")
    except Exception as e:
        print(f"❌ 評論生成失敗: {e}")


# --- 4. 遊戲主迴圈 ---

def run_game():
    """遊戲的主流程控制。"""
    state = load_state()
    
    MAX_DAYS = 3 # 運行幾個回合作為範例
    
    while state['player']['days_passed'] < MAX_DAYS and state['player']['gold'] > 0:
        day = state['player']['days_passed'] + 1
        print(f"\n==================== Day {day} Start ====================")
        print(f"💰 金幣: {state['player']['gold']} | 🌟 聲望: {state['player']['reputation_level']}")
        
        # 步驟 1: 任務生成
        state = task_1_quest_generation(state)
        
        # 步驟 2: 配方分析與消化 (LLM 消化自身輸入)
        state = task_2_recipe_digest(state)
        
        # 步驟 3: 玩家行動 (這裡需要使用者輸入)
        missing_list = state['current_quest'].get('missing', {})
        if missing_list:
            print(f"\n💡 助手提示：您缺少以下材料：{missing_list}")
            action = input(">>> 您決定採取什麼行動來獲取材料？ (輸入行動敘述): ")
            state = task_3_action_evaluation(state, action)
        else:
            print("\n💡 助手提示：材料齊全，開始煉製！")
            # 如果沒有缺少材料，可以跳過行動，直接進入交易/煉製環節
            state['player']['gold'] -= 5 # 假設煉製需要耗費金幣
        
        # 步驟 4: 任務交付與更新
        state = task_4_transaction_update(state)
        
        # 回合結束
        state['player']['days_passed'] = day
        save_state(state)
        time.sleep(1) # 避免 API 呼叫過快
        
    print("\n==================== 遊戲結束 ====================")
    
    # 步驟 5: 最終評論
    task_5_final_review(state['game_log'])
    
    print(f"\n遊戲日誌已儲存，請檢查 {STATE_FILE} 和 {REVIEW_FILE}。")


if __name__ == "__main__":
    run_game()