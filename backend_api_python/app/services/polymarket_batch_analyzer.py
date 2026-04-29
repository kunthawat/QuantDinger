"""
Polymarket批量分析器
一次性分析多个市场，由AI筛选出有交易机会的市场
"""
import json
from typing import List, Dict, Optional
from app.utils.logger import get_logger
from app.utils.db import get_db_connection
from app.services.llm import LLMService
from app.data_sources.polymarket import PolymarketDataSource

logger = get_logger(__name__)


class PolymarketBatchAnalyzer:
    """批量分析预测市场，由AI筛选交易机会"""
    
    def __init__(self):
        self.llm_service = LLMService()
        self.polymarket_source = PolymarketDataSource()
    
    def batch_analyze_markets(self, markets: List[Dict], max_opportunities: int = 20) -> List[Dict]:
        """
        批量分析市场，由AI筛选出有交易机会的市场
        
        Args:
            markets: 市场列表
            max_opportunities: 最多返回多少个交易机会
            
        Returns:
            筛选后的市场列表（包含AI分析结果）
        """
        if not markets:
            return []
        
        try:
            # 1. 构建批量分析的prompt
            markets_summary = self._build_markets_summary(markets)
            
            prompt = f"""You are a professional prediction market analyst. Analyze the following list of prediction markets and filter for the best trading opportunities.

Markets:
{markets_summary}

Evaluate each market based on these dimensions:
1. **Market Activity**: Is trading volume and liquidity sufficient?
2. **Probability Divergence**: Is the current market probability deviating from a reasonable expectation? (Deviation from 50%, the larger the better)
3. **Event Importance**: How significant is the event's impact?
4. **Time Window**: Is the time until settlement appropriate (not too close or too far)?
5. **Information Edge**: Is there obvious information asymmetry or market mispricing?

Return JSON format with filtered market IDs and brief analysis:
{{
    "opportunities": [
        {{
            "market_id": "market_id",
            "opportunity_score": 85,  // Opportunity score 0-100
            "reason": "Why this market has trading opportunity (brief explanation)",
            "recommendation": "YES/NO/HOLD",  // Recommended direction
            "confidence": 75,  // Confidence level 0-100
            "key_factors": ["Factor 1", "Factor 2"]  // Key factors
        }}
    ]
}}

Requirements:
- Return only the top {max_opportunities} opportunities
- Only consider opportunities with score >= 60
- Prioritize: high volume + clear probability divergence + high confidence
- Keep explanations brief, do not be verbose"""

            # 2. Call LLM for batch analysis
            messages = [
                {
                    "role": "system",
                    "content": "You are a professional prediction market analyst skilled at quickly identifying valuable trading opportunities from a large set of markets. Be objective and rational. Only recommend truly advantageous opportunities."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            logger.info(f"Batch analyzing {len(markets)} markets, requesting {max_opportunities} opportunities")
            result = self.llm_service.call_llm_api(
                messages=messages,
                use_json_mode=True,
                temperature=0.3
            )
            
            # 3. 解析结果
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except:
                    logger.error(f"Failed to parse LLM result as JSON: {result[:200]}")
                    return self._fallback_analysis(markets, max_opportunities)
            
            opportunities = result.get('opportunities', [])
            if not opportunities:
                logger.warning("LLM returned no opportunities, using fallback")
                return self._fallback_analysis(markets, max_opportunities)
            
            # 4. 将AI分析结果合并到市场数据中
            opportunities_map = {opp.get('market_id'): opp for opp in opportunities}
            analyzed_markets = []
            
            for market in markets:
                market_id = market.get('market_id')
                if not market_id:
                    continue
                
                opp = opportunities_map.get(market_id)
                if opp:
                    # 获取AI预测的概率
                    predicted_prob = float(opp.get('predicted_probability', market.get('current_probability', 50.0)))
                    market_prob = market.get('current_probability', 50.0)
                    divergence = predicted_prob - market_prob
                    
                    # 合并AI分析结果
                    market['ai_analysis'] = {
                        'predicted_probability': predicted_prob,  # 使用AI预测的概率
                        'recommendation': opp.get('recommendation', 'HOLD'),
                        'confidence_score': float(opp.get('confidence', 0)),
                        'opportunity_score': float(opp.get('opportunity_score', 0)),
                        'divergence': divergence,  # AI预测概率 - 市场概率
                        'reasoning': opp.get('reason', ''),
                        'key_factors': opp.get('key_factors', [])
                    }
                    analyzed_markets.append(market)
            
            # 5. 按机会评分排序
            analyzed_markets.sort(
                key=lambda x: x.get('ai_analysis', {}).get('opportunity_score', 0),
                reverse=True
            )
            
            logger.info(f"Batch analysis completed: {len(analyzed_markets)} opportunities identified")
            return analyzed_markets
            
        except Exception as e:
            error_msg = str(e)
            # Provide more helpful error messages for common API errors
            if "403" in error_msg or "Forbidden" in error_msg:
                logger.error(
                    f"Batch analysis failed: OpenRouter API 403 Forbidden. "
                    f"请检查：1) OPENROUTER_API_KEY 是否正确配置 2) API 密钥是否有效 3) 账户余额是否充足。"
                    f"错误详情: {error_msg}"
                )
            elif "401" in error_msg or "Unauthorized" in error_msg:
                logger.error(
                    f"Batch analysis failed: OpenRouter API 401 Unauthorized. "
                    f"OPENROUTER_API_KEY 无效或已过期。请检查 backend_api_python/.env 中的配置。"
                    f"错误详情: {error_msg}"
                )
            else:
                logger.error(f"Batch analysis failed: {error_msg}", exc_info=True)
            return self._fallback_analysis(markets, max_opportunities)
    
    def _build_markets_summary(self, markets: List[Dict]) -> str:
        """构建市场摘要，用于批量分析"""
        summary_lines = []
        
        for i, market in enumerate(markets[:50], 1):  # 限制最多50个，避免prompt过长
            market_id = market.get('market_id', '')
            question = market.get('question', '')[:100]  # 限制长度
            prob = market.get('current_probability', 50.0)
            volume = market.get('volume_24h', 0)
            category = market.get('category', 'other')
            
            summary_lines.append(
                f"{i}. ID: {market_id}\n"
                f"   问题: {question}\n"
                f"   当前概率: {prob:.1f}%\n"
                f"   24h交易量: ${volume:,.0f}\n"
                f"   分类: {category}"
            )
        
        return "\n\n".join(summary_lines)
    
    def _fallback_analysis(self, markets: List[Dict], max_opportunities: int) -> List[Dict]:
        """回退分析：基于简单规则筛选"""
        opportunities = []
        
        for market in markets:
            prob = market.get('current_probability', 50.0)
            volume = market.get('volume_24h', 0)
            
            # 简单规则：交易量大 + 概率偏离50%
            if volume > 10000 and abs(prob - 50.0) > 10:
                opportunity_score = min(60 + abs(prob - 50.0) * 0.5, 90)
                
                market['ai_analysis'] = {
                    'predicted_probability': prob,
                    'recommendation': 'YES' if prob > 50 else 'NO',
                    'confidence_score': 60.0,
                    'opportunity_score': opportunity_score,
                    'divergence': 0,
                    'reasoning': f'高交易量({volume:,.0f}) + 明显概率偏差({prob:.1f}%)',
                    'key_factors': ['高交易量', '概率偏差']
                }
                opportunities.append(market)
        
        # 按机会评分排序
        opportunities.sort(
            key=lambda x: x.get('ai_analysis', {}).get('opportunity_score', 0),
            reverse=True
        )
        
        return opportunities[:max_opportunities]
    
    def save_batch_analysis(self, markets: List[Dict]):
        """保存批量分析结果到数据库"""
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                
                for market in markets:
                    market_id = market.get('market_id')
                    ai_analysis = market.get('ai_analysis')
                    
                    if not market_id or not ai_analysis:
                        continue
                    
                    try:
                        # 先删除该市场的旧分析记录（user_id为NULL的通用分析）
                        cur.execute("""
                            DELETE FROM qd_polymarket_ai_analysis
                            WHERE market_id = %s AND user_id IS NULL
                        """, (market_id,))
                        
                        # 插入新的分析记录
                        cur.execute("""
                            INSERT INTO qd_polymarket_ai_analysis
                            (market_id, user_id, ai_predicted_probability, market_probability,
                             divergence, recommendation, confidence_score, opportunity_score,
                             reasoning, key_factors, related_assets, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        """, (
                            market_id,
                            None,  # 通用分析
                            float(ai_analysis.get('predicted_probability', market.get('current_probability', 50.0))),
                            market.get('current_probability', 50.0),
                            float(ai_analysis.get('divergence', 0)),
                            ai_analysis.get('recommendation', 'HOLD'),
                            ai_analysis.get('confidence_score', 0),
                            ai_analysis.get('opportunity_score', 0),
                            ai_analysis.get('reasoning', ''),
                            json.dumps(ai_analysis.get('key_factors', [])),
                            []
                        ))
                    except Exception as e:
                        logger.warning(f"Failed to save analysis for market {market_id}: {e}")
                        continue
                
                db.commit()
                cur.close()
                logger.info(f"Saved batch analysis for {len(markets)} markets")
                
        except Exception as e:
            logger.error(f"Failed to save batch analysis: {e}", exc_info=True)
