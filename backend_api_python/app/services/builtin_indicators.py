"""
Built-in sample indicators written for new users on registration (editable/deletable).

Idempotent via the first indicator's name: skips if it already exists, avoiding
duplicate insert edge cases with create_user etc.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

from app.utils.logger import get_logger

logger = get_logger(__name__)


def _builtin_specs() -> List[Dict[str, str]]:
    """Built-in indicators: name / description / code (matches indicator IDE and backtest engine contract)."""
    return [
        {
            "name": "[Sample] RSI Edge Trigger",
            "description": "Classic RSI oversold bounce buy and overbought reversal sell. Signal fires on bar-close to avoid duplicate entries. Good for learning the backtest panel and @strategy.",
            "code": r'''my_indicator_name = "[Sample] RSI Edge Trigger"
my_indicator_description = "RSI oversold/overbought with edge trigger; adjust leverage, timeframe and symbol in the backtest panel."

# @strategy stopLossPct 0.03
# @strategy takeProfitPct 0.06
# @strategy entryPct 1
# @strategy tradeDirection long

df = df.copy()
rsi_len = 14
delta = df['close'].diff()
gain = delta.clip(lower=0)
loss = (-delta).clip(lower=0)
avg_gain = gain.ewm(alpha=1 / rsi_len, adjust=False).mean()
avg_loss = loss.ewm(alpha=1 / rsi_len, adjust=False).mean()
rs = avg_gain / avg_loss.replace(0, np.nan)
rsi = 100 - (100 / (1 + rs))
rsi = rsi.fillna(50)

raw_buy = rsi < 30
raw_sell = rsi > 70
buy = raw_buy.fillna(False) & (~raw_buy.shift(1).fillna(False))
sell = raw_sell.fillna(False) & (~raw_sell.shift(1).fillna(False))
df['buy'] = buy.astype(bool)
df['sell'] = sell.astype(bool)

buy_marks = [df['low'].iloc[i] * 0.995 if bool(buy.iloc[i]) else None for i in range(len(df))]
sell_marks = [df['high'].iloc[i] * 1.005 if bool(sell.iloc[i]) else None for i in range(len(df))]

output = {
    'name': my_indicator_name,
    'plots': [
        {'name': 'RSI(14)', 'data': rsi.tolist(), 'color': '#faad14', 'overlay': False}
    ],
    'signals': [
        {'type': 'buy', 'text': 'B', 'data': buy_marks, 'color': '#00E676'},
        {'type': 'sell', 'text': 'S', 'data': sell_marks, 'color': '#FF5252'}
    ]
}
''',
        },
        {
            "name": "[Sample] Dual MA Crossover",
            "description": "Buy when fast MA crosses above slow MA, sell on the reverse. Edit fast/slow periods directly in the code.",
            "code": r'''my_indicator_name = "[Sample] Dual MA Crossover"
my_indicator_description = "Fast/slow MA crossover; edge trigger. Leverage and fees are set in the backtest panel."

# @strategy stopLossPct 0.025
# @strategy takeProfitPct 0.05
# @strategy entryPct 1
# @strategy tradeDirection both

df = df.copy()
fast_n = 12
slow_n = 26
ma_f = df['close'].rolling(fast_n, min_periods=1).mean()
ma_s = df['close'].rolling(slow_n, min_periods=1).mean()

golden = (ma_f > ma_s) & (ma_f.shift(1) <= ma_s.shift(1))
death = (ma_f < ma_s) & (ma_f.shift(1) >= ma_s.shift(1))
df['buy'] = golden.fillna(False).astype(bool)
df['sell'] = death.fillna(False).astype(bool)

buy_marks = [df['low'].iloc[i] * 0.995 if bool(df['buy'].iloc[i]) else None for i in range(len(df))]
sell_marks = [df['high'].iloc[i] * 1.005 if bool(df['sell'].iloc[i]) else None for i in range(len(df))]

output = {
    'name': my_indicator_name,
    'plots': [
        {'name': f'MA({fast_n})', 'data': ma_f.tolist(), 'color': '#1890ff', 'overlay': True},
        {'name': f'MA({slow_n})', 'data': ma_s.tolist(), 'color': '#ff7a45', 'overlay': True}
    ],
    'signals': [
        {'type': 'buy', 'text': 'B', 'data': buy_marks, 'color': '#00E676'},
        {'type': 'sell', 'text': 'S', 'data': sell_marks, 'color': '#FF5252'}
    ]
}
''',
        },
        {
            "name": "[Sample] MACD Histogram Zero Cross",
            "description": "Go long when MACD histogram crosses above zero; go short when it crosses below. Useful for observing momentum shifts.",
            "code": r'''my_indicator_name = "[Sample] MACD Histogram Zero Cross"
my_indicator_description = "DIF/DEA/Hist; histogram crossing zero axis with edge trigger. Pairs well with 1H/4H crypto futures backtest."

# @strategy stopLossPct 0.03
# @strategy takeProfitPct 0.08
# @strategy entryPct 0.5
# @strategy tradeDirection both

df = df.copy()
exp12 = df['close'].ewm(span=12, adjust=False).mean()
exp26 = df['close'].ewm(span=26, adjust=False).mean()
dif = exp12 - exp26
dea = dif.ewm(span=9, adjust=False).mean()
hist = dif - dea

raw_buy = (hist > 0) & (hist.shift(1) <= 0)
raw_sell = (hist < 0) & (hist.shift(1) >= 0)
df['buy'] = raw_buy.fillna(False).astype(bool)
df['sell'] = raw_sell.fillna(False).astype(bool)

buy_marks = [df['low'].iloc[i] * 0.995 if bool(df['buy'].iloc[i]) else None for i in range(len(df))]
sell_marks = [df['high'].iloc[i] * 1.005 if bool(df['sell'].iloc[i]) else None for i in range(len(df))]

output = {
    'name': my_indicator_name,
    'plots': [
        {'name': 'MACD DIF', 'data': dif.tolist(), 'color': '#1890ff', 'overlay': False},
        {'name': 'MACD DEA', 'data': dea.tolist(), 'color': '#ff7a45', 'overlay': False},
        {'name': 'MACD Hist', 'data': hist.tolist(), 'color': '#888888', 'overlay': False}
    ],
    'signals': [
        {'type': 'buy', 'text': 'B', 'data': buy_marks, 'color': '#00E676'},
        {'type': 'sell', 'text': 'S', 'data': sell_marks, 'color': '#FF5252'}
    ]
}
''',
        },
        {
            "name": "[Sample] Bollinger Band Touch",
            "description": "Buy when close touches the lower band, sell on upper band touch (edge trigger). For backtesting only — add trend filter and risk management for live trading.",
            "code": r'''my_indicator_name = "[Sample] Bollinger Band Touch"
my_indicator_description = "Simple Bollinger Band reversal sample; combine with trend filter and risk management for live trading."

# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.04
# @strategy entryPct 0.3
# @strategy tradeDirection long

df = df.copy()
period = 20
mult = 2.0
mid = df['close'].rolling(period, min_periods=1).mean()
std = df['close'].rolling(period, min_periods=1).std()
upper = mid + mult * std
lower = mid - mult * std

raw_buy = df['close'] < lower
raw_sell = df['close'] > upper
buy = raw_buy.fillna(False) & (~raw_buy.shift(1).fillna(False))
sell = raw_sell.fillna(False) & (~raw_sell.shift(1).fillna(False))
df['buy'] = buy.astype(bool)
df['sell'] = sell.astype(bool)

buy_marks = [df['low'].iloc[i] * 0.995 if bool(buy.iloc[i]) else None for i in range(len(df))]
sell_marks = [df['high'].iloc[i] * 1.005 if bool(sell.iloc[i]) else None for i in range(len(df))]

output = {
    'name': my_indicator_name,
    'plots': [
        {'name': 'BOLL Upper', 'data': upper.tolist(), 'color': '#69c0ff', 'overlay': True},
        {'name': 'BOLL Mid', 'data': mid.tolist(), 'color': '#d9d9d9', 'overlay': True},
        {'name': 'BOLL Lower', 'data': lower.tolist(), 'color': '#69c0ff', 'overlay': True}
    ],
    'signals': [
        {'type': 'buy', 'text': 'B', 'data': buy_marks, 'color': '#00E676'},
        {'type': 'sell', 'text': 'S', 'data': sell_marks, 'color': '#FF5252'}
    ]
}
''',
        },
    ]


# 与 _builtin_specs()[0]["name"] 一致，用于注册时幂等判断
_BUILTIN_PACK_ANCHOR_NAME = "[Sample] RSI Edge Trigger"


def seed_builtin_indicators_for_new_user(db: Any, user_id: int) -> int:
    """
    注册成功后写入示例指标包。若该用户已有锚点名称指标则跳过（幂等）。
    返回本次插入条数。
    """
    if not user_id:
        return 0
    now = int(time.time())
    cur = db.cursor()
    try:
        cur.execute(
            """
            SELECT 1 AS x
            FROM qd_indicator_codes
            WHERE user_id = ? AND name = ?
            LIMIT 1
            """,
            (user_id, _BUILTIN_PACK_ANCHOR_NAME),
        )
        if cur.fetchone():
            return 0

        inserted = 0
        for spec in _builtin_specs():
            cur.execute(
                """
                INSERT INTO qd_indicator_codes
                  (user_id, is_buy, end_time, name, code, description,
                   publish_to_community, pricing_type, price, preview_image, vip_free, review_status,
                   createtime, updatetime, created_at, updated_at)
                VALUES (?, 0, 1, ?, ?, ?, 0, 'free', 0, '', FALSE, NULL, ?, ?, NOW(), NOW())
                """,
                (
                    user_id,
                    spec["name"],
                    spec["code"],
                    spec["description"],
                    now,
                    now,
                ),
            )
            inserted += 1
        db.commit()
        if inserted:
            logger.info("Seeded %s builtin indicator(s) for new user_id=%s", inserted, user_id)
        return inserted
    except Exception as e:
        logger.warning("seed_builtin_indicators_for_new_user failed user_id=%s: %s", user_id, e)
        try:
            db.rollback()
        except Exception:
            pass
        return 0
    finally:
        try:
            cur.close()
        except Exception:
            pass
