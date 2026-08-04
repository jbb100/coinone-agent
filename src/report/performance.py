"""TWR(시간가중수익률) — 입출금을 수익에서 분리하는 순수 함수.

'30일 총자산 변화율'은 입금과 수익이 섞여 전략 성과를 오도한다.
TWR은 일별 수익률 r_t = (V_t − flow_t) / V_{t−1} − 1 을 연쇄해
외부 현금 흐름의 영향을 제거한다.

외부 흐름 추정의 한계: 시스템은 입출금을 직접 기록하지 않으므로
KRW 잔고 변화와 거래 내역으로 역산한다
(flow = ΔKRW + 매수 − 매도). 코인 자체의 외부 이체(콜드월렛 출금 등)는
가격 변동과 구분할 수 없어 수익률로 오인된다 — 코인 이체가 있었던 달의
TWR은 신뢰하지 말 것 (DEPLOYMENT.md 콜드월렛 수칙 참고).
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class DailyPoint:
    date: str               # YYYY-MM-DD
    total_value_krw: float
    krw_balance: float


def infer_external_flow(
    prev: DailyPoint, cur: DailyPoint, buys_krw: float, sells_krw: float
) -> float:
    """외부 입출금 추정 = ΔKRW + 매수 − 매도.

    매수는 KRW를 줄이고 매도는 늘리는 내부 전환이므로 되돌려서
    순수 외부 흐름만 남긴다.
    """
    return (cur.krw_balance - prev.krw_balance) + buys_krw - sells_krw


def compute_twr(
    points: List[DailyPoint],
    trades_by_date: Dict[str, Tuple[float, float]],
) -> Optional[Tuple[float, int]]:
    """(TWR 수익률, 관측 창 일수) — 유효 스냅샷 2개 미만이면 None.

    trades_by_date: {날짜: (매수 KRW, 매도 KRW)}.
    총자산 0인 스냅샷(수집 실패 잔재)은 버리고 나머지를 연쇄한다.
    """
    valid = [p for p in points if p.total_value_krw > 0]
    if len(valid) < 2:
        return None
    growth = 1.0
    for prev, cur in zip(valid, valid[1:]):
        buys, sells = trades_by_date.get(cur.date, (0.0, 0.0))
        flow = infer_external_flow(prev, cur, buys, sells)
        growth *= (cur.total_value_krw - flow) / prev.total_value_krw
    days = (
        datetime.strptime(valid[-1].date, "%Y-%m-%d")
        - datetime.strptime(valid[0].date, "%Y-%m-%d")
    ).days
    return growth - 1.0, max(days, 1)
