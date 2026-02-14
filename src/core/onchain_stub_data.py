"""
온체인 데이터 스텁 (STUB DATA)

Glassnode/CryptoQuant 등 유료 API 연동 전까지 사용되는 예시 데이터입니다.
실제 트레이딩 시 이 데이터에 의존하면 안 됩니다.

TODO: 실제 API 연동 시 이 파일 제거 또는 테스트용으로만 유지
"""

from typing import Dict

# 고래 데이터 (BTC 기준)
WHALE_DATA = {
    "count": 2150,           # 고래 주소 수
    "balance": 8500000,      # 고래 총 보유량 (BTC)
    "flow": 2500,            # 24시간 순 흐름 (양수 = 축적)
}

# 거래소 흐름 데이터
EXCHANGE_DATA = {
    "inflow": 25000,         # 거래소 유입량
    "outflow": 28000,        # 거래소 유출량
    "reserves": 2800000,     # 거래소 보유량
}

# 장기/단기 보유자 데이터
HOLDER_DATA = {
    "lth_supply": 68.5,      # 장기보유자 공급량 (%)
    "lth_position_change": 150,  # 장기보유자 포지션 변화 (BTC)
}

# 네트워크 활동 데이터
NETWORK_DATA = {
    "active_addresses": 750000,   # 활성 주소 수
    "hash_rate": 450.5,           # 해시레이트 (EH/s)
    "transaction_count": 280000,  # 일일 트랜잭션 수
    "nvl": 450000000000,          # 네트워크 잠금 가치 (USD)
}

# 스테이블코인 데이터
STABLECOIN_DATA = {
    "supply": 130000000000,       # 총 공급량 (USD)
    "dominance": 8.5,             # 도미넌스 (%)
    "flow": 2500000000,           # 24시간 흐름 (USD)
}

# 펀딩 비율 데이터
FUNDING_RATES = {
    "binance": 0.0025,
    "bybit": 0.0030,
    "okx": 0.0020,
}


def get_stub_data(category: str, key: str):
    """스텁 데이터 조회 헬퍼"""
    data_map = {
        "whale": WHALE_DATA,
        "exchange": EXCHANGE_DATA,
        "holder": HOLDER_DATA,
        "network": NETWORK_DATA,
        "stablecoin": STABLECOIN_DATA,
        "funding": FUNDING_RATES,
    }
    return data_map.get(category, {}).get(key)
