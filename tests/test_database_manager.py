"""
Database Manager Tests

데이터베이스 매니저 테스트
"""

import pytest
import os
import tempfile
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.utils.database_manager import DatabaseManager, serialize_for_json


@pytest.mark.database
class TestSerializeForJson:
    """JSON 직렬화 헬퍼 함수 테스트"""

    def test_serialize_datetime(self):
        """datetime 직렬화"""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = serialize_for_json(dt)

        assert result == "2024-01-15T10:30:00"

    def test_serialize_numpy_int(self):
        """numpy int 직렬화"""
        import numpy as np
        value = np.int64(12345)
        result = serialize_for_json(value)

        assert result == 12345
        assert isinstance(result, int)

    def test_serialize_numpy_float(self):
        """numpy float 직렬화"""
        import numpy as np
        value = np.float64(3.14159)
        result = serialize_for_json(value)

        assert abs(result - 3.14159) < 0.0001
        assert isinstance(result, float)

    def test_serialize_dict(self):
        """딕셔너리 직렬화"""
        data = {
            "timestamp": datetime(2024, 1, 1),
            "value": 100
        }
        result = serialize_for_json(data)

        assert result["timestamp"] == "2024-01-01T00:00:00"
        assert result["value"] == 100

    def test_serialize_list(self):
        """리스트 직렬화"""
        data = [datetime(2024, 1, 1), 100, "text"]
        result = serialize_for_json(data)

        assert result[0] == "2024-01-01T00:00:00"
        assert result[1] == 100
        assert result[2] == "text"

    def test_serialize_nested(self):
        """중첩 구조 직렬화"""
        data = {
            "outer": {
                "inner": [datetime(2024, 1, 1)]
            }
        }
        result = serialize_for_json(data)

        assert result["outer"]["inner"][0] == "2024-01-01T00:00:00"

    def test_serialize_regular_types(self):
        """일반 타입은 그대로 반환"""
        assert serialize_for_json("text") == "text"
        assert serialize_for_json(100) == 100
        assert serialize_for_json(3.14) == 3.14
        assert serialize_for_json(None) is None


@pytest.mark.database
class TestDatabaseManagerInit:
    """DatabaseManager 초기화 테스트"""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """임시 데이터베이스 경로"""
        return str(tmp_path / "test.db")

    @pytest.fixture
    def mock_config(self, temp_db_path):
        """Mock 설정"""
        config = Mock()
        config.get = Mock(return_value=temp_db_path)
        return config

    def test_init_creates_database(self, mock_config, temp_db_path):
        """초기화 시 데이터베이스 생성"""
        db_manager = DatabaseManager(mock_config)

        assert os.path.exists(temp_db_path)

    def test_init_creates_directory(self, tmp_path):
        """디렉토리 자동 생성"""
        db_path = str(tmp_path / "subdir" / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)

        db_manager = DatabaseManager(config)

        assert os.path.exists(os.path.dirname(db_path))

    def test_init_creates_tables(self, mock_config, temp_db_path):
        """테이블 생성 확인"""
        import sqlite3

        db_manager = DatabaseManager(mock_config)

        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        assert "market_analysis" in tables
        assert "portfolio_snapshots" in tables
        assert "trade_history" in tables
        assert "trading_locks" in tables


@pytest.mark.database
class TestDatabaseManagerConnection:
    """데이터베이스 연결 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_get_connection_success(self, db_manager):
        """연결 성공"""
        with db_manager.get_connection() as conn:
            assert conn is not None
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

    def test_get_connection_row_factory(self, db_manager):
        """Row factory 설정 확인"""
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE test (id INTEGER, name TEXT)")
            cursor.execute("INSERT INTO test VALUES (1, 'test')")
            cursor.execute("SELECT * FROM test")
            row = cursor.fetchone()

            # Row factory로 컬럼명 접근 가능
            assert row["id"] == 1
            assert row["name"] == "test"


@pytest.mark.database
class TestMarketAnalysis:
    """시장 분석 저장/조회 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_save_market_analysis(self, db_manager):
        """시장 분석 저장"""
        analysis_result = {
            "analysis_date": datetime.now().isoformat(),
            "market_season": "risk_on",
            "season_changed": False,
            "analysis_info": {
                "current_price": 50000000,
                "ma_200w": 40000000,
                "price_ratio": 1.25
            },
            "allocation_weights": {
                "crypto": 0.7,
                "krw": 0.3
            }
        }

        record_id = db_manager.save_market_analysis(analysis_result)

        assert record_id > 0

    def test_get_latest_market_analysis(self, db_manager):
        """최근 시장 분석 조회"""
        # 데이터 저장
        analysis_result = {
            "analysis_date": datetime.now().isoformat(),
            "market_season": "risk_on",
            "allocation_weights": {"crypto": 0.7, "krw": 0.3}
        }
        db_manager.save_market_analysis(analysis_result)

        # 조회
        result = db_manager.get_latest_market_analysis()

        assert result is not None
        assert result["market_season"] == "risk_on"

    def test_get_latest_market_analysis_empty(self, db_manager):
        """데이터 없을 때 조회"""
        result = db_manager.get_latest_market_analysis()

        assert result is None

    def test_save_multiple_analyses(self, db_manager):
        """여러 분석 저장 후 최신 조회"""
        # 첫 번째 분석
        db_manager.save_market_analysis({
            "analysis_date": (datetime.now() - timedelta(days=1)).isoformat(),
            "market_season": "neutral"
        })

        # 두 번째 분석 (더 최신)
        db_manager.save_market_analysis({
            "analysis_date": datetime.now().isoformat(),
            "market_season": "risk_on"
        })

        result = db_manager.get_latest_market_analysis()

        assert result["market_season"] == "risk_on"


@pytest.mark.database
class TestRebalanceResult:
    """리밸런싱 결과 저장 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_save_rebalance_result(self, db_manager):
        """리밸런싱 결과 저장"""
        rebalance_result = {
            "timestamp": datetime.now().isoformat(),
            "success": True,
            "total_value_before": 1000000,
            "total_value_after": 1050000,
            "executed_orders": [{"asset": "BTC", "status": "filled"}],
            "failed_orders": [],
            "rebalance_summary": {
                "market_season": "risk_on",
                "value_change": 50000
            }
        }

        record_id = db_manager.save_rebalance_result(rebalance_result)

        assert record_id > 0

    def test_save_rebalance_result_minimal(self, db_manager):
        """최소 정보로 저장"""
        rebalance_result = {
            "success": False,
            "rebalance_summary": {}
        }

        record_id = db_manager.save_rebalance_result(rebalance_result)

        assert record_id > 0


@pytest.mark.database
class TestTradeHistory:
    """거래 내역 조회 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_get_trade_history_empty(self, db_manager):
        """빈 거래 내역 조회"""
        history = db_manager.get_trade_history(days=30)

        assert isinstance(history, list)


@pytest.mark.database
class TestPortfolioSnapshot:
    """포트폴리오 스냅샷 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_get_portfolio_history_empty(self, db_manager):
        """빈 포트폴리오 히스토리 조회"""
        history = db_manager.get_portfolio_history(days=30)

        assert isinstance(history, list)


@pytest.mark.database
class TestTradingLocks:
    """거래 락 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_acquire_trading_lock(self, db_manager):
        """거래 락 획득"""
        lock_id = db_manager.acquire_trading_lock(
            lock_type="rebalancing",
            asset="BTC",
            duration_hours=2,
            reason="Test lock"
        )

        assert lock_id is not None

    def test_release_trading_lock(self, db_manager):
        """거래 락 해제"""
        lock_id = db_manager.acquire_trading_lock(
            lock_type="rebalancing",
            asset="BTC",
            duration_hours=2
        )

        result = db_manager.release_trading_lock(lock_id)

        assert result is True

    def test_acquire_multiple_locks(self, db_manager):
        """여러 락 획득"""
        lock1 = db_manager.acquire_trading_lock("rebalancing", "BTC", 2)
        lock2 = db_manager.acquire_trading_lock("twap", "ETH", 1)

        assert lock1 != lock2
        assert lock1 > 0
        assert lock2 > 0

    def test_release_nonexistent_lock(self, db_manager):
        """존재하지 않는 락 해제 시도"""
        result = db_manager.release_trading_lock(99999)

        # 존재하지 않는 락 해제는 False 또는 에러 없이 처리
        assert isinstance(result, bool)


@pytest.mark.database
class TestOpportunisticBuyLimits:
    """기회적 매수 한도 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_update_daily_buy_limits(self, db_manager):
        """일일 매수 한도 업데이트"""
        result = db_manager.update_daily_buy_limits(
            asset="BTC",
            amount=100000,
            price=50000000
        )

        # 업데이트 성공 확인
        assert result is None or result is True

    def test_get_daily_buy_stats(self, db_manager):
        """일일 매수 통계 조회"""
        db_manager.update_daily_buy_limits(
            asset="BTC",
            amount=100000,
            price=50000000
        )

        stats = db_manager.get_daily_buy_stats("BTC")

        assert stats is not None
        assert isinstance(stats, dict)

    def test_get_recent_opportunistic_buys(self, db_manager):
        """최근 기회적 매수 조회"""
        buys = db_manager.get_recent_opportunistic_buys("BTC", hours=4)

        assert isinstance(buys, list)


@pytest.mark.database
class TestAdvancedAnalysis:
    """고급 분석 결과 저장 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_save_analysis_result(self, db_manager):
        """분석 결과 저장"""
        record_id = db_manager.save_analysis_result(
            analysis_type="multi_timeframe",
            result_data={
                "trend": "bullish",
                "strength": 0.8
            }
        )

        assert record_id > 0

    def test_get_latest_analysis_result(self, db_manager):
        """최근 분석 결과 조회"""
        db_manager.save_analysis_result(
            analysis_type="macro_economic",
            result_data={"risk_level": "low"}
        )

        result = db_manager.get_latest_analysis_result("macro_economic")

        assert result is not None

    def test_get_all_latest_analysis_results(self, db_manager):
        """모든 최근 분석 결과 조회"""
        db_manager.save_analysis_result("type1", {"data": 1})
        db_manager.save_analysis_result("type2", {"data": 2})

        results = db_manager.get_all_latest_analysis_results()

        assert isinstance(results, dict)


@pytest.mark.database
class TestTwapOrders:
    """TWAP 주문 관련 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_get_latest_rebalance_record(self, db_manager):
        """최근 리밸런싱 기록 조회"""
        # 데이터 없는 경우 테스트
        result = db_manager.get_latest_rebalance_record()

        # None이거나 딕셔너리
        assert result is None or isinstance(result, dict)

    def test_get_active_twap_executions(self, db_manager):
        """활성 TWAP 실행 조회"""
        executions = db_manager.get_active_twap_executions()

        assert isinstance(executions, list)

    def test_get_latest_active_twap_execution(self, db_manager):
        """최신 활성 TWAP 실행 조회"""
        result = db_manager.get_latest_active_twap_execution()

        # None이거나 딕셔너리
        assert result is None or isinstance(result, dict)


@pytest.mark.database
class TestDatabaseManagerEdgeCases:
    """엣지 케이스 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_save_with_special_characters(self, db_manager):
        """특수 문자 포함 데이터 저장"""
        analysis_result = {
            "market_season": "risk_on",
            "notes": "테스트 'quotes' and \"double quotes\" & special <chars>"
        }

        record_id = db_manager.save_market_analysis(analysis_result)

        assert record_id > 0

    def test_save_with_none_values(self, db_manager):
        """None 값 포함 데이터 저장"""
        analysis_result = {
            "market_season": "neutral",  # None이 아닌 값 사용
            "analysis_info": {
                "current_price": None
            }
        }

        record_id = db_manager.save_market_analysis(analysis_result)

        assert record_id > 0

    def test_save_with_large_data(self, db_manager):
        """큰 데이터 저장"""
        large_data = {
            "market_season": "risk_on",
            "large_array": list(range(10000))  # 큰 배열
        }

        record_id = db_manager.save_market_analysis(large_data)

        assert record_id > 0

    def test_concurrent_access(self, db_manager):
        """동시 접근 테스트"""
        import threading

        results = []

        def save_data(i):
            try:
                record_id = db_manager.save_market_analysis({
                    "market_season": f"test_{i}"
                })
                results.append(record_id)
            except Exception as e:
                results.append(e)

        threads = [
            threading.Thread(target=save_data, args=(i,))
            for i in range(5)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # 모든 저장 성공
        success_count = sum(1 for r in results if isinstance(r, int) and r > 0)
        assert success_count == 5


@pytest.mark.database
class TestDatabaseManagerQuery:
    """조회 관련 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_get_rebalance_history(self, db_manager):
        """리밸런싱 히스토리 조회"""
        # 데이터 저장
        for i in range(3):
            db_manager.save_rebalance_result({
                "timestamp": (datetime.now() - timedelta(days=i)).isoformat(),
                "success": True,
                "rebalance_summary": {"market_season": f"season_{i}"}
            })

        history = db_manager.get_rebalance_history(limit=2)

        assert len(history) == 2

    def test_get_portfolio_history(self, db_manager):
        """포트폴리오 히스토리 조회"""
        # 히스토리 조회 (데이터 없음)
        history = db_manager.get_portfolio_history(days=7)

        assert isinstance(history, list)
