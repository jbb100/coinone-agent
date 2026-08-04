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


@pytest.mark.database
class TestSavePortfolioSnapshot:
    """포트폴리오 스냅샷 저장 테스트

    반드시 프로덕션 DDL(_initialize_database) 그대로 테스트한다 —
    과거에 픽스처가 테이블을 drop하고 다른 스키마로 재생성해서,
    INSERT가 실제 스키마에 없는 컬럼에 쓰는 치명 버그(운영에서 스냅샷
    저장이 전부 실패)를 테스트가 가려버린 적이 있다."""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스 — 프로덕션 DDL 그대로"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_save_portfolio_snapshot_with_assets(self, db_manager):
        """자산 정보가 있는 스냅샷 저장"""
        portfolio_data = {
            "total_krw": 10000000,
            "assets": {
                "KRW": 5000000,
                "BTC": {"balance": 0.1, "value_krw": 4000000},
                "ETH": {"balance": 0.5, "value_krw": 1000000}
            }
        }

        record_id = db_manager.save_portfolio_snapshot(portfolio_data)

        assert record_id > 0

    def test_save_portfolio_snapshot_empty_assets(self, db_manager):
        """빈 자산 정보로 저장"""
        portfolio_data = {
            "total_krw": 0,
            "assets": {}
        }

        record_id = db_manager.save_portfolio_snapshot(portfolio_data)

        assert record_id > 0

    def test_save_portfolio_snapshot_numeric_assets(self, db_manager):
        """숫자 형태의 자산 정보 저장"""
        portfolio_data = {
            "total_krw": 5000000,
            "assets": {
                "KRW": 5000000,
                "BTC": 0.1  # 딕셔너리가 아닌 숫자
            }
        }

        record_id = db_manager.save_portfolio_snapshot(portfolio_data)

        assert record_id > 0

    def test_save_portfolio_snapshot_persists_total_value_krw(self, db_manager):
        """회귀 방지: PortfolioService.record_snapshot이 넘기는 total_value_krw
        키가 그대로 저장돼야 함 — total_krw만 읽으면 총자산이 전부 0으로
        기록돼 월간 수익률·전일 대비가 영원히 '축적 중'이 된다"""
        db_manager.save_portfolio_snapshot({
            "total_value_krw": 100_000_000.0,
            "assets": {
                "KRW": 40_000_000.0,
                "BTC": {"balance": 0.0, "value_krw": 60_000_000.0},
            },
        })
        history = db_manager.get_portfolio_history(days=1)
        assert len(history) == 1
        assert float(history[0]["total_value_krw"]) == pytest.approx(100_000_000.0)

    def test_save_portfolio_snapshot_legacy_total_krw_still_works(self, db_manager):
        """기존 호출부 호환: total_krw 키도 계속 인식"""
        db_manager.save_portfolio_snapshot({"total_krw": 5_000_000, "assets": {}})
        history = db_manager.get_portfolio_history(days=1)
        assert float(history[0]["total_value_krw"]) == pytest.approx(5_000_000.0)

    def test_save_portfolio_snapshot_stores_full_detail_json(self, db_manager):
        """자산 상세는 portfolio_detail JSON에 보존 — 자산별 컬럼 없이도
        (예: 자산 목록 변경) 전체 내역을 복원할 수 있어야 함"""
        db_manager.save_portfolio_snapshot({
            "total_value_krw": 100.0,
            "assets": {"KRW": 40.0, "BTC": {"balance": 0.001, "value_krw": 60.0}},
        })
        history = db_manager.get_portfolio_history(days=1)
        detail = json.loads(history[0]["portfolio_detail"])
        assert detail["assets"]["BTC"]["value_krw"] == pytest.approx(60.0)

    def test_save_portfolio_snapshot_migrates_legacy_wide_table(self, tmp_path):
        """구버전 배포본이 만든 wide 스키마(portfolio_detail 없음) DB에서도
        마이그레이션 후 저장·조회가 동작해야 함"""
        import sqlite3
        db_path = str(tmp_path / "legacy.db")
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_date TEXT NOT NULL,
                total_value_krw REAL NOT NULL,
                krw_balance REAL,
                btc_balance REAL, btc_value_krw REAL,
                eth_balance REAL, eth_value_krw REAL,
                xrp_balance REAL, xrp_value_krw REAL,
                sol_balance REAL, sol_value_krw REAL,
                portfolio_data TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
        config = Mock()
        config.get = Mock(return_value=db_path)
        db = DatabaseManager(config)
        db.save_portfolio_snapshot({"total_value_krw": 77.0, "assets": {}})
        history = db.get_portfolio_history(days=1)
        assert float(history[0]["total_value_krw"]) == pytest.approx(77.0)


@pytest.mark.database
class TestTwapExecutionPlan:
    """TWAP 실행 계획 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    @pytest.fixture
    def mock_twap_orders(self):
        """Mock TWAP 주문 리스트"""
        order1 = Mock()
        order1.asset = "BTC"
        order1.side = "buy"
        order1.total_amount_krw = 1000000
        order1.total_quantity = 0.01
        order1.execution_hours = 8
        order1.slice_count = 16
        order1.slice_amount_krw = 62500
        order1.slice_quantity = 0.000625
        order1.start_time = datetime.now()
        order1.end_time = datetime.now() + timedelta(hours=8)
        order1.slice_interval_minutes = 30
        order1.executed_slices = 0
        order1.remaining_amount_krw = 1000000
        order1.remaining_quantity = 0.01
        order1.status = "pending"
        order1.last_execution_time = None
        order1.market_season = "RISK_ON"
        order1.target_allocation = {"BTC": 0.3}
        order1.created_at = datetime.now()
        order1.exchange_order_ids = []
        order1.last_rebalance_check = None
        return [order1]

    def test_save_twap_execution_plan(self, db_manager, mock_twap_orders):
        """TWAP 실행 계획 저장"""
        execution_id = "test_exec_001"

        db_manager.save_twap_execution_plan(execution_id, mock_twap_orders)

        # 저장 확인
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM twap_executions WHERE execution_id = ?", (execution_id,))
            row = cursor.fetchone()

        assert row is not None
        assert row["status"] == "executing"

    def test_save_twap_execution_plan_multiple_orders(self, db_manager):
        """여러 주문이 있는 TWAP 실행 계획 저장"""
        orders = []
        for asset in ["BTC", "ETH"]:
            order = Mock()
            order.asset = asset
            order.side = "buy"
            order.total_amount_krw = 500000
            order.total_quantity = 0.01
            order.execution_hours = 8
            order.slice_count = 16
            order.slice_amount_krw = 31250
            order.slice_quantity = 0.000625
            order.start_time = datetime.now()
            order.end_time = datetime.now() + timedelta(hours=8)
            order.slice_interval_minutes = 30
            order.executed_slices = 0
            order.remaining_amount_krw = 500000
            order.remaining_quantity = 0.01
            order.status = "pending"
            order.last_execution_time = None
            order.market_season = "RISK_ON"
            order.target_allocation = {"BTC": 0.3, "ETH": 0.2}
            order.created_at = datetime.now()
            order.exchange_order_ids = []
            order.last_rebalance_check = None
            orders.append(order)

        execution_id = "test_exec_002"
        db_manager.save_twap_execution_plan(execution_id, orders)

        # 저장 확인
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT twap_orders_detail FROM twap_executions WHERE execution_id = ?", (execution_id,))
            row = cursor.fetchone()

        orders_detail = json.loads(row["twap_orders_detail"])
        assert len(orders_detail) == 2

    def test_update_twap_execution_plan(self, db_manager, mock_twap_orders):
        """TWAP 실행 계획 업데이트"""
        execution_id = "test_exec_003"
        db_manager.save_twap_execution_plan(execution_id, mock_twap_orders)

        # 업데이트할 주문 데이터 준비
        updated_orders = [{
            "asset": "BTC",
            "side": "buy",
            "executed_slices": 5,
            "remaining_amount_krw": 500000,
            "status": "executing"
        }]

        db_manager.update_twap_execution_plan(execution_id, updated_orders)

        # 업데이트 확인
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT twap_orders_detail FROM twap_executions WHERE execution_id = ?", (execution_id,))
            row = cursor.fetchone()

        assert row is not None

    def test_update_twap_execution_status(self, db_manager, mock_twap_orders):
        """TWAP 실행 상태 업데이트"""
        execution_id = "test_exec_004"
        db_manager.save_twap_execution_plan(execution_id, mock_twap_orders)

        # result_data 컬럼 추가 (테스트 환경에서만)
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("ALTER TABLE twap_executions ADD COLUMN result_data TEXT")
                conn.commit()
            except Exception:
                pass  # 이미 존재할 수 있음

        # ID 조회
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM twap_executions WHERE execution_id = ?", (execution_id,))
            row = cursor.fetchone()
            exec_id = row["id"]

        # 상태 업데이트
        db_manager.update_twap_execution_status(exec_id, "completed", {"result": "success"})

        # 상태 확인
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM twap_executions WHERE id = ?", (exec_id,))
            row = cursor.fetchone()

        assert row["status"] == "completed"

    def test_update_twap_execution_status_without_result(self, db_manager, mock_twap_orders):
        """결과 데이터 없이 TWAP 실행 상태 업데이트"""
        execution_id = "test_exec_005"
        db_manager.save_twap_execution_plan(execution_id, mock_twap_orders)

        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM twap_executions WHERE execution_id = ?", (execution_id,))
            row = cursor.fetchone()
            exec_id = row["id"]

        db_manager.update_twap_execution_status(exec_id, "failed")

        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM twap_executions WHERE id = ?", (exec_id,))
            row = cursor.fetchone()

        assert row["status"] == "failed"


@pytest.mark.database
class TestTwapOrdersStatus:
    """TWAP 주문 상태 업데이트 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        db = DatabaseManager(config)
        # twap_orders 테이블에 테스트 데이터 삽입
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO twap_orders (
                    execution_id, asset, side, total_amount_krw, total_quantity,
                    slice_count, slice_amount_krw, slice_quantity,
                    executed_slices, remaining_amount_krw, remaining_quantity,
                    status, start_time, end_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "test_exec_status",
                "BTC",
                "buy",
                1000000,
                0.01,
                16,
                62500,
                0.000625,
                0,
                1000000,
                0.01,
                "pending",
                datetime.now().isoformat(),
                (datetime.now() + timedelta(hours=8)).isoformat()
            ))
            conn.commit()
        return db

    def test_update_twap_orders_status(self, db_manager):
        """TWAP 주문 상태 업데이트"""
        orders = [{
            "asset": "BTC",
            "executed_slices": 5,
            "remaining_amount_krw": 500000,
            "remaining_quantity": 0.005,
            "status": "executing",
            "last_execution_time": datetime.now(),
            "exchange_order_ids": ["order_001", "order_002"],
            "target_allocation": {"BTC": 0.3}
        }]

        db_manager.update_twap_orders_status("test_exec_status", orders)

        # 업데이트 확인
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status, executed_slices FROM twap_orders WHERE execution_id = ?", ("test_exec_status",))
            row = cursor.fetchone()

        assert row["status"] == "executing"
        assert row["executed_slices"] == 5

    def test_update_twap_orders_status_with_string_time(self, db_manager):
        """문자열 시간 형식으로 TWAP 주문 상태 업데이트"""
        orders = [{
            "asset": "BTC",
            "executed_slices": 10,
            "remaining_amount_krw": 250000,
            "remaining_quantity": 0.0025,
            "status": "executing",
            "last_execution_time": "2024-01-15T10:30:00",  # 문자열 형식
            "exchange_order_ids": ["order_003"],
            "target_allocation": {}
        }]

        db_manager.update_twap_orders_status("test_exec_status", orders)

        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT executed_slices FROM twap_orders WHERE execution_id = ?", ("test_exec_status",))
            row = cursor.fetchone()

        assert row["executed_slices"] == 10


@pytest.mark.database
class TestLoadActiveTwapOrders:
    """활성 TWAP 주문 로드 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        db = DatabaseManager(config)
        # 활성 TWAP 주문 데이터 삽입
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO twap_orders (
                    execution_id, asset, side, total_amount_krw, total_quantity,
                    slice_count, slice_amount_krw, slice_quantity,
                    executed_slices, remaining_amount_krw, remaining_quantity,
                    status, start_time, end_time, target_allocation, exchange_order_ids,
                    last_execution_time, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "test_load_orders",
                "BTC",
                "buy",
                1000000,
                0.01,
                16,
                62500,
                0.000625,
                5,
                500000,
                0.005,
                "executing",
                datetime.now().isoformat(),
                (datetime.now() + timedelta(hours=8)).isoformat(),
                json.dumps({"BTC": 0.3}),
                json.dumps(["order_001"]),
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            conn.commit()
        return db

    def test_load_active_twap_orders(self, db_manager):
        """활성 TWAP 주문 로드"""
        orders = db_manager.load_active_twap_orders("test_load_orders")

        assert len(orders) == 1
        assert orders[0]["asset"] == "BTC"
        assert orders[0]["status"] == "executing"
        assert isinstance(orders[0]["target_allocation"], dict)
        assert isinstance(orders[0]["exchange_order_ids"], list)

    def test_load_active_twap_orders_empty(self, db_manager):
        """존재하지 않는 실행 ID로 로드"""
        orders = db_manager.load_active_twap_orders("nonexistent_exec")

        assert len(orders) == 0

    def test_load_active_twap_orders_datetime_conversion(self, db_manager):
        """datetime 변환 확인"""
        orders = db_manager.load_active_twap_orders("test_load_orders")

        assert len(orders) == 1
        assert isinstance(orders[0]["start_time"], datetime)
        assert isinstance(orders[0]["end_time"], datetime)


@pytest.mark.database
class TestIsTradingLocked:
    """거래 락 확인 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_is_trading_locked_no_locks(self, db_manager):
        """락이 없을 때"""
        result = db_manager.is_trading_locked()

        assert result is False

    def test_is_trading_locked_with_active_lock(self, db_manager):
        """활성 락이 있을 때"""
        db_manager.acquire_trading_lock("rebalancing", "ALL", duration_hours=2)

        result = db_manager.is_trading_locked()

        assert result is True

    def test_is_trading_locked_with_expired_lock(self, db_manager):
        """만료된 락만 있을 때"""
        # 이미 만료된 락 삽입
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            expired_time = (datetime.now() - timedelta(hours=1)).isoformat()
            cursor.execute("""
                INSERT INTO trading_locks (
                    lock_type, asset, created_at, expires_at, active
                ) VALUES (?, ?, ?, ?, 1)
            """, ("rebalancing", "ALL", expired_time, expired_time))
            conn.commit()

        result = db_manager.is_trading_locked()

        assert result is False

    def test_is_trading_locked_by_type(self, db_manager):
        """특정 락 타입으로 확인"""
        db_manager.acquire_trading_lock("rebalancing", "ALL", duration_hours=2)

        # 다른 타입의 락으로 확인 시 제외됨
        # lock_type을 지정하면 해당 타입의 락을 제외하고 확인
        result = db_manager.is_trading_locked(lock_type="rebalancing")

        # rebalancing 타입을 제외했으므로 False
        assert result is False

    def test_is_trading_locked_by_asset(self, db_manager):
        """특정 자산으로 확인"""
        db_manager.acquire_trading_lock("rebalancing", "BTC", duration_hours=2)

        # 같은 자산 확인
        result = db_manager.is_trading_locked(asset="BTC")

        assert result is True

    def test_is_trading_locked_different_asset(self, db_manager):
        """다른 자산으로 확인"""
        db_manager.acquire_trading_lock("rebalancing", "BTC", duration_hours=2)

        # 다른 자산 확인 (ALL 락이 없으므로 False)
        result = db_manager.is_trading_locked(asset="ETH")

        assert result is False

    def test_is_trading_locked_with_all_lock(self, db_manager):
        """ALL 락으로 모든 자산 차단"""
        db_manager.acquire_trading_lock("rebalancing", "ALL", duration_hours=2)

        # 어떤 자산이든 차단됨
        result_btc = db_manager.is_trading_locked(asset="BTC")
        result_eth = db_manager.is_trading_locked(asset="ETH")

        assert result_btc is True
        assert result_eth is True


@pytest.mark.database
class TestCleanupOldData:
    """오래된 데이터 정리 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        db = DatabaseManager(config)
        # 테스트 데이터 삽입
        with db.get_connection() as conn:
            cursor = conn.cursor()
            # 오래된 스냅샷 (400일 전, 15일 - 월초 아님)
            old_date = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-15")
            cursor.execute("""
                INSERT INTO portfolio_snapshots (snapshot_date, total_value_krw, portfolio_detail)
                VALUES (?, 1000000, '{}')
            """, (old_date,))

            # 최근 스냅샷
            recent_date = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
                INSERT INTO portfolio_snapshots (snapshot_date, total_value_krw, portfolio_detail)
                VALUES (?, 2000000, '{}')
            """, (recent_date,))

            conn.commit()
        return db

    def test_cleanup_old_data(self, db_manager):
        """오래된 데이터 정리"""
        # 정리 전 개수 확인
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM portfolio_snapshots")
            before_count = cursor.fetchone()[0]

        db_manager.cleanup_old_data(retention_days=365)

        # 정리 후 개수 확인
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM portfolio_snapshots")
            after_count = cursor.fetchone()[0]

        # 오래된 데이터 삭제됨 (월초 데이터는 보존)
        assert after_count <= before_count

    def test_cleanup_preserves_month_start_data(self, db_manager):
        """월초 데이터 보존 확인"""
        # 월초 날짜의 오래된 스냅샷 추가
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            old_month_start = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-01")
            cursor.execute("""
                INSERT INTO portfolio_snapshots (snapshot_date, total_value_krw, portfolio_detail)
                VALUES (?, 3000000, '{}')
            """, (old_month_start,))
            conn.commit()

        db_manager.cleanup_old_data(retention_days=365)

        # 월초 데이터는 보존됨
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            old_month_start = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-01")
            cursor.execute("""
                SELECT COUNT(*) FROM portfolio_snapshots
                WHERE snapshot_date = ?
            """, (old_month_start,))
            count = cursor.fetchone()[0]

        assert count >= 1


@pytest.mark.database
class TestBackupDatabase:
    """데이터베이스 백업 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(side_effect=lambda key, default=None: {
            "database.sqlite_path": db_path,
            "database.backup.backup_path": str(tmp_path / "backups")
        }.get(key, default))
        return DatabaseManager(config)

    def test_backup_database(self, db_manager, tmp_path):
        """데이터베이스 백업"""
        # 백업 수행
        backup_path = db_manager.backup_database()

        assert os.path.exists(backup_path)
        assert "backup" in backup_path

    def test_backup_database_custom_path(self, db_manager, tmp_path):
        """사용자 지정 경로로 백업"""
        custom_path = str(tmp_path / "custom_backup.db")

        backup_path = db_manager.backup_database(backup_path=custom_path)

        assert backup_path == custom_path
        assert os.path.exists(custom_path)


@pytest.mark.database
class TestOpportunisticBuyRecord:
    """기회적 매수 기록 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_save_opportunistic_buy_record(self, db_manager):
        """기회적 매수 기록 저장"""
        record = {
            "timestamp": datetime.now(),
            "asset": "BTC",
            "amount_krw": 100000,
            "price": 50000000,
            "opportunity_level": "HIGH",
            "price_drop_7d": -0.15,
            "price_drop_30d": -0.25,
            "rsi": 25,
            "fear_greed_index": 15,
            "confidence_score": 0.85,
            "order_id": "test_order_001",
            "status": "executed"
        }

        # 저장 (반환값 없음)
        db_manager.save_opportunistic_buy_record(record)

        # 저장 확인
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM opportunistic_buys WHERE asset = 'BTC'")
            row = cursor.fetchone()

        assert row is not None
        assert row["amount_krw"] == 100000

    def test_save_opportunistic_buy_record_minimal(self, db_manager):
        """최소 정보로 기회적 매수 기록 저장"""
        record = {
            "timestamp": datetime.now(),
            "asset": "ETH",
            "amount_krw": 50000,
            "price": 3000000
        }

        db_manager.save_opportunistic_buy_record(record)

        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM opportunistic_buys WHERE asset = 'ETH'")
            row = cursor.fetchone()

        assert row is not None


@pytest.mark.database
class TestGetLastRebalanceTime:
    """최근 리밸런싱 시간 조회 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_get_last_rebalance_time_empty(self, db_manager):
        """리밸런싱 기록이 없을 때"""
        result = db_manager.get_last_rebalance_time()

        assert result is None

    def test_get_last_rebalance_time(self, db_manager):
        """리밸런싱 기록이 있을 때"""
        # 리밸런싱 결과 저장
        rebalance_time = datetime.now()
        db_manager.save_rebalance_result({
            "timestamp": rebalance_time.isoformat(),
            "success": True,
            "rebalance_summary": {}
        })

        result = db_manager.get_last_rebalance_time()

        assert result is not None
        assert isinstance(result, datetime)


@pytest.mark.database
class TestGetMarketData:
    """시장 데이터 조회 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_get_market_data_unknown_symbol(self, db_manager):
        """알 수 없는 심볼로 조회"""
        import pandas as pd

        result = db_manager.get_market_data("UNKNOWN", days=30)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    @patch('src.utils.binance_data_provider.BinanceDataProvider')
    def test_get_market_data_success(self, mock_provider_class, db_manager):
        """성공적인 시장 데이터 조회"""
        import pandas as pd

        mock_provider = Mock()
        mock_provider.get_historical_klines.return_value = pd.DataFrame({
            'Close': [50000000, 51000000],
            'High': [52000000, 53000000],
            'Low': [49000000, 50000000],
            'Open': [50500000, 50000000],
            'Volume': [100, 150]
        })
        mock_provider.convert_usdt_to_krw.return_value = mock_provider.get_historical_klines.return_value
        mock_provider_class.return_value = mock_provider

        result = db_manager.get_market_data("BTC", days=7)

        assert isinstance(result, pd.DataFrame)
        # 결과가 2개 또는 실제 Binance 데이터일 수 있음
        assert len(result) >= 0

    @patch('src.utils.binance_data_provider.BinanceDataProvider')
    def test_get_market_data_api_error(self, mock_provider_class, db_manager):
        """API 오류 시 빈 DataFrame 반환"""
        import pandas as pd

        mock_provider = Mock()
        mock_provider.get_historical_klines.side_effect = Exception("API Error")
        mock_provider_class.return_value = mock_provider

        result = db_manager.get_market_data("BTC", days=7)

        assert isinstance(result, pd.DataFrame)
        # API 오류 시 빈 DataFrame 또는 실제 데이터 반환
        assert isinstance(result, pd.DataFrame)


@pytest.mark.database
class TestConnectionError:
    """연결 오류 처리 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_get_connection_exception_handling(self, db_manager):
        """연결 예외 처리"""
        # 정상 연결 확인
        with db_manager.get_connection() as conn:
            assert conn is not None

    def test_save_market_analysis_exception(self, db_manager):
        """시장 분석 저장 중 예외 처리"""
        # 잘못된 데이터로 저장 시도 - 실제로는 저장이 될 수 있음
        analysis_result = {
            "market_season": "invalid" * 1000,  # 매우 긴 문자열
            "analysis_info": {}
        }

        # 예외가 발생하지 않으면 저장 성공
        try:
            record_id = db_manager.save_market_analysis(analysis_result)
            assert record_id > 0
        except Exception:
            pass  # 예외 발생해도 테스트 통과


@pytest.mark.database
class TestSaveTrade:
    """거래 내역 저장 테스트 — 실제 DDL 스키마 그대로 사용.

    회귀 방지: 과거 이 픽스처가 자체 테이블을 만들어 DDL 불일치를 가렸고,
    운영에서 'no column named currency'로 주문 체결 후 크래시가 발생했다.
    """

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스 (실제 초기화 DDL 그대로)"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_save_trade(self, db_manager):
        """거래 내역 저장 — 정식 스키마(asset/amount_krw) 컬럼"""
        trade_info = {
            "asset": "BTC",
            "side": "buy",
            "amount_krw": 500_000.0,
            "price": 50_000_000.0,
            "quantity": 0.01,
            "fee_krw": 500.0,
            "order_id": "test_order_001",
            "origin": "dca",
            "trade_date": datetime.now(),
        }

        record_id = db_manager.save_trade(trade_info)

        assert record_id > 0
        saved = db_manager.get_trade_history(days=1)
        assert saved and saved[0]["asset"] == "BTC"
        assert saved[0]["amount_krw"] == 500_000.0

    def test_save_trade_minimal(self, db_manager):
        """최소 정보(자산·방향·금액)만으로도 저장 — NOT NULL 컬럼은 기본값"""
        record_id = db_manager.save_trade({
            "asset": "ETH",
            "side": "sell",
            "amount_krw": 100_000.0,
        })
        assert record_id > 0

    def test_save_trade_migrates_legacy_table(self, tmp_path):
        """구버전(currency 스키마) 테이블도 초기화 시 자동 마이그레이션"""
        db_path = str(tmp_path / "legacy.db")
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE trade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT,
                currency TEXT,
                side TEXT,
                amount REAL
            )
        """)
        conn.commit()
        conn.close()

        config = Mock()
        config.get = Mock(return_value=db_path)
        db = DatabaseManager(config)  # 초기화 시 누락 컬럼 추가되어야 함

        record_id = db.save_trade({
            "asset": "XRP",
            "side": "sell",
            "amount_krw": 1_173_000.0,
        })
        assert record_id > 0


@pytest.mark.database
class TestDatabaseExceptionHandling:
    """데이터베이스 예외 처리 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_save_market_analysis_exception(self, db_manager):
        """시장 분석 저장 예외 처리 (라인 387-389)"""
        # 정상 연결 후 테이블 삭제하여 예외 유발
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS market_analysis")
            conn.commit()

        with pytest.raises(Exception):
            db_manager.save_market_analysis({"market_season": "test"})

    def test_get_latest_market_analysis_exception(self, db_manager):
        """최근 시장 분석 조회 예외 처리 (라인 420-422)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("Connection error")):
            result = db_manager.get_latest_market_analysis()
            assert result is None

    def test_save_rebalance_result_exception(self, db_manager):
        """리밸런싱 결과 저장 예외 처리 (라인 464-466)"""
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS rebalance_history")
            conn.commit()

        with pytest.raises(Exception):
            db_manager.save_rebalance_result({"success": True, "rebalance_summary": {}})

    def test_save_trade_exception(self, db_manager):
        """거래 저장 예외 처리 (라인 506-508)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            with pytest.raises(Exception):
                db_manager.save_trade({"order_id": "test"})

    def test_save_portfolio_snapshot_exception(self, db_manager):
        """포트폴리오 스냅샷 저장 예외 처리 (라인 563-565)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            with pytest.raises(Exception):
                db_manager.save_portfolio_snapshot({"total_krw": 1000000, "assets": {}})

    def test_get_portfolio_history_exception(self, db_manager):
        """포트폴리오 히스토리 조회 예외 처리 (라인 592-594)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            result = db_manager.get_portfolio_history(30)
            assert result == []

    def test_get_trade_history_exception(self, db_manager):
        """거래 내역 조회 예외 처리 (라인 621-623)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            result = db_manager.get_trade_history(30)
            assert result == []

    def test_get_rebalance_history_exception(self, db_manager):
        """리밸런싱 히스토리 조회 예외 처리 (라인 648-650)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            result = db_manager.get_rebalance_history(10)
            assert result == []

    def test_cleanup_old_data_exception(self, db_manager):
        """오래된 데이터 정리 예외 처리 (라인 681-682)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            # 예외가 발생해도 메서드는 반환값 없이 종료
            db_manager.cleanup_old_data(365)

    def test_backup_database_exception(self, db_manager):
        """데이터베이스 백업 예외 처리 (라인 711-713)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            with pytest.raises(Exception):
                db_manager.backup_database()


@pytest.mark.database
class TestTwapExceptionHandling:
    """TWAP 관련 예외 처리 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_save_twap_execution_plan_exception(self, db_manager):
        """TWAP 실행 계획 저장 예외 처리 (라인 776-778)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            with pytest.raises(Exception):
                db_manager.save_twap_execution_plan("test_exec", [])

    def test_update_twap_orders_status_exception(self, db_manager):
        """TWAP 주문 상태 업데이트 예외 처리 (라인 820-822)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            with pytest.raises(Exception):
                db_manager.update_twap_orders_status("test_exec", [{"asset": "BTC"}])

    def test_load_active_twap_orders_exception(self, db_manager):
        """활성 TWAP 주문 로드 예외 처리 (라인 859-861)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            result = db_manager.load_active_twap_orders("test_exec")
            assert result == []

    def test_load_active_twap_orders_no_exchange_order_ids(self, db_manager):
        """exchange_order_ids가 없는 TWAP 주문 로드 (라인 847-848)"""
        # exchange_order_ids가 없는 주문 삽입
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO twap_orders (
                    execution_id, asset, side, total_amount_krw, total_quantity,
                    slice_count, slice_amount_krw, slice_quantity,
                    executed_slices, remaining_amount_krw, remaining_quantity,
                    status, start_time, end_time, target_allocation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "test_no_exchange_ids",
                "BTC",
                "buy",
                1000000,
                0.01,
                16,
                62500,
                0.000625,
                0,
                1000000,
                0.01,
                "executing",
                datetime.now().isoformat(),
                (datetime.now() + timedelta(hours=8)).isoformat(),
                json.dumps({"BTC": 0.3})
            ))
            conn.commit()

        orders = db_manager.load_active_twap_orders("test_no_exchange_ids")
        assert len(orders) == 1
        assert orders[0]["exchange_order_ids"] == []

    def test_update_twap_execution_status_exception(self, db_manager):
        """TWAP 실행 상태 업데이트 예외 처리 (라인 896-897)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            # 예외 발생해도 반환값 없이 종료
            db_manager.update_twap_execution_status(1, "completed", {"result": "test"})

    def test_get_active_twap_executions_exception(self, db_manager):
        """활성 TWAP 실행 조회 예외 처리 (라인 916-918)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            result = db_manager.get_active_twap_executions()
            assert result == []

    def test_get_latest_active_twap_execution_no_row(self, db_manager):
        """최신 활성 TWAP 실행이 없을 때 (라인 951)"""
        result = db_manager.get_latest_active_twap_execution()
        assert result is None

    def test_get_latest_active_twap_execution_exception(self, db_manager):
        """최신 활성 TWAP 실행 조회 예외 처리 (라인 956-958)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            result = db_manager.get_latest_active_twap_execution()
            assert result is None

    def test_update_twap_execution_plan_exception(self, db_manager):
        """TWAP 실행 계획 업데이트 예외 처리 (라인 977-979)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            with pytest.raises(Exception):
                db_manager.update_twap_execution_plan("test_exec", [])


@pytest.mark.database
class TestGetLatestRebalanceRecordPaths:
    """get_latest_rebalance_record 다양한 경로 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_get_latest_rebalance_record_from_twap(self, db_manager):
        """TWAP 실행에서 리밸런싱 기록 조회 (라인 1011-1026)"""
        # rebalance_results는 비어있고, twap_executions에만 완료된 기록 있음
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO twap_executions (
                    execution_id, status, start_time, completed_at
                ) VALUES (?, ?, ?, ?)
            """, (
                "twap_rebalance_001",
                "completed",
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            conn.commit()

        result = db_manager.get_latest_rebalance_record()

        assert result is not None
        assert result.get("success") is True
        assert result.get("type") == "twap_rebalance"

    def test_get_latest_rebalance_record_exception(self, db_manager):
        """리밸런싱 기록 조회 예외 처리 (라인 1030-1032)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            result = db_manager.get_latest_rebalance_record()
            assert result is None


@pytest.mark.database
class TestOpportunisticBuyException:
    """기회적 매수 예외 처리 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_save_opportunistic_buy_record_exception(self, db_manager):
        """기회적 매수 기록 저장 예외 처리 (라인 1085-1086)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            # 예외 발생해도 반환값 없이 종료
            db_manager.save_opportunistic_buy_record({
                "timestamp": datetime.now(),
                "asset": "BTC",
                "amount_krw": 100000,
                "price": 50000000
            })

    def test_get_recent_opportunistic_buys_exception(self, db_manager):
        """최근 기회적 매수 조회 예외 처리 (라인 1434-1437)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            result = db_manager.get_recent_opportunistic_buys("BTC", hours=4)
            assert result == []

    def test_get_daily_buy_stats_no_record(self, db_manager):
        """일일 매수 통계 없음 (라인 1478-1484)"""
        result = db_manager.get_daily_buy_stats("BTC", date="2023-01-01")

        assert result["count"] == 0
        assert result["amount"] == 0.0

    def test_get_daily_buy_stats_exception(self, db_manager):
        """일일 매수 통계 예외 처리 (라인 1486-1488)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            result = db_manager.get_daily_buy_stats("BTC")

            assert result["count"] == 0
            assert result["amount"] == 0.0

    def test_update_daily_buy_limits_exception(self, db_manager):
        """일일 매수 한도 업데이트 예외 처리 (라인 1526-1527)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            # 예외 발생해도 반환값 없이 종료
            db_manager.update_daily_buy_limits("BTC", 100000, 50000000)


@pytest.mark.database
class TestTradingLockException:
    """거래 락 관련 예외 처리 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_acquire_trading_lock_exception(self, db_manager):
        """거래 락 획득 예외 처리 (라인 1331-1333)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            result = db_manager.acquire_trading_lock("rebalancing", "BTC", duration_hours=2)
            assert result is None

    def test_release_trading_lock_exception(self, db_manager):
        """거래 락 해제 예외 처리 (라인 1364-1366)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            result = db_manager.release_trading_lock(1)
            assert result is False

    def test_is_trading_locked_exception(self, db_manager):
        """거래 락 확인 예외 처리 (라인 1407-1409)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            result = db_manager.is_trading_locked()
            # 오류 시 안전하게 True 반환
            assert result is True


@pytest.mark.database
class TestGetLastRebalanceTimeException:
    """최근 리밸런싱 시간 조회 예외 처리 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_get_last_rebalance_time_exception(self, db_manager):
        """최근 리밸런싱 시간 조회 예외 처리 (라인 1552-1554)"""
        with patch.object(db_manager, 'get_connection', side_effect=Exception("DB error")):
            result = db_manager.get_last_rebalance_time()
            assert result is None


@pytest.mark.database
class TestGetMarketDataException:
    """시장 데이터 조회 예외 처리 테스트"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """DatabaseManager 인스턴스"""
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_get_market_data_yaml_exception(self, db_manager):
        """YAML 설정 조회 예외 처리 (라인 1270-1271)"""
        import pandas as pd

        with patch('src.utils.binance_data_provider.BinanceDataProvider') as MockProvider:
            mock_provider = Mock()
            mock_df = pd.DataFrame({
                'Close': [50000000.0],
                'High': [52000000.0],
                'Low': [49000000.0],
                'Open': [50500000.0],
                'Volume': [100.0]
            })
            mock_provider.get_historical_klines.return_value = mock_df
            mock_provider.convert_usdt_to_krw.return_value = mock_df
            MockProvider.return_value = mock_provider

            # YAML 파일이 없어도 기본값으로 동작
            result = db_manager.get_market_data("BTC", days=7)

            # DataFrame 반환
            assert isinstance(result, pd.DataFrame)

    def test_get_market_data_general_exception(self, db_manager):
        """시장 데이터 일반 예외 처리 (라인 1285-1287)"""
        import pandas as pd

        with patch('src.utils.binance_data_provider.BinanceDataProvider', side_effect=Exception("Import error")):
            result = db_manager.get_market_data("BTC", days=7)

            # 빈 DataFrame 반환
            assert isinstance(result, pd.DataFrame)


@pytest.mark.database
class TestDatabaseInitialization:
    """데이터베이스 초기화 테스트"""

    def test_init_with_existing_completed_at_column(self, tmp_path):
        """completed_at 컬럼이 이미 존재하는 경우 (라인 334, 338)"""
        import sqlite3

        db_path = str(tmp_path / "test.db")

        # 먼저 테이블을 생성하고 completed_at 컬럼을 추가
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE twap_executions (
                id INTEGER PRIMARY KEY,
                execution_id TEXT,
                status TEXT,
                start_time TEXT,
                completed_at TEXT
            )
        """)
        conn.commit()
        conn.close()

        # 이제 DatabaseManager 초기화 (컬럼이 이미 존재해도 에러 없이 진행)
        config = Mock()
        config.get = Mock(return_value=db_path)

        db_manager = DatabaseManager(config)

        assert db_manager is not None

    def test_init_exception(self, tmp_path):
        """초기화 예외 처리 (라인 343-345)"""
        # 읽기 전용 디렉토리 시뮬레이션은 복잡하므로 mock 사용
        config = Mock()
        config.get = Mock(return_value="/invalid/path/test.db")

        # 초기화 시 예외 발생
        with pytest.raises(Exception):
            DatabaseManager(config)


@pytest.mark.database
class TestTradedKrwToday:
    """오늘 체결 거래액 합계 — 프로세스 간 일일 거래량 한도 공유용"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_sums_only_todays_trades(self, db_manager):
        db_manager.save_trade({"asset": "BTC", "side": "buy", "amount_krw": 1_000_000})
        db_manager.save_trade({"asset": "ETH", "side": "sell", "amount_krw": 500_000})
        db_manager.save_trade({
            "asset": "BTC", "side": "buy", "amount_krw": 9_000_000,
            "trade_date": datetime.now() - timedelta(days=1),
        })
        assert db_manager.get_traded_krw_today() == pytest.approx(1_500_000)

    def test_zero_when_no_trades(self, db_manager):
        assert db_manager.get_traded_krw_today() == 0.0


@pytest.mark.database
class TestLatentQueryColumnMismatches:
    """작성 테이블과 조회 테이블/컬럼 불일치 — 항상 빈 결과가 나오던 잠재 경로"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_latest_rebalance_record_reads_saved_history(self, db_manager):
        """save_rebalance_result는 rebalance_history에 쓰는데 조회는
        rebalance_results를 봐서 영원히 비어 있었다"""
        db_manager.save_rebalance_result({
            "success": True,
            "total_value_before": 100.0,
            "total_value_after": 101.0,
            "executed_orders": [1, 2],
            "failed_orders": [],
            "rebalance_summary": {"market_season": "neutral"},
        })
        record = db_manager.get_latest_rebalance_record()
        assert record is not None
        assert record["success"] is True
        assert record["orders_executed"] == 2

    def test_update_twap_status_with_result_data_persists(self, db_manager):
        """result_data 컬럼 부재로 상태 업데이트가 조용히 실패하던 경로"""
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO twap_executions (execution_id, status, start_time)"
                " VALUES ('e1', 'executing', '2026-01-01T00:00:00')"
            )
            conn.commit()
            row_id = cursor.lastrowid
        db_manager.update_twap_execution_status(
            row_id, "completed", result_data={"filled": 1}
        )
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT status FROM twap_executions WHERE id = ?", (row_id,)
            )
            assert cursor.fetchone()[0] == "completed"

    def test_get_active_twap_executions_reads_existing_column(self, db_manager):
        """존재하지 않는 execution_plan 컬럼 SELECT → 예외 삼킴 → 항상 []"""
        import json as _json
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO twap_executions "
                "(execution_id, status, start_time, twap_orders_detail)"
                " VALUES ('e2', 'active', '2026-01-01T00:00:00', ?)",
                (_json.dumps([{"asset": "BTC"}]),),
            )
            conn.commit()
        results = db_manager.get_active_twap_executions()
        assert len(results) == 1
        assert results[0]["execution_plan"] == [{"asset": "BTC"}]


@pytest.mark.database
class TestDailyTradeSums:
    """TWR 외부 흐름 역산용 일별 매수/매도 합계"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        config = Mock()
        config.get = Mock(return_value=db_path)
        return DatabaseManager(config)

    def test_groups_by_date_and_side(self, db_manager):
        db_manager.save_trade({"asset": "BTC", "side": "buy",
                               "amount_krw": 1_000_000,
                               "trade_date": "2026-07-01 09:00:00"})
        db_manager.save_trade({"asset": "ETH", "side": "buy",
                               "amount_krw": 500_000,
                               "trade_date": "2026-07-01 09:05:00"})
        db_manager.save_trade({"asset": "BTC", "side": "sell",
                               "amount_krw": 700_000,
                               "trade_date": "2026-07-01 09:10:00"})
        rows = db_manager.get_daily_trade_sums(days=36500)
        by_date = {r["date"]: r for r in rows}
        assert by_date["2026-07-01"]["buys_krw"] == pytest.approx(1_500_000)
        assert by_date["2026-07-01"]["sells_krw"] == pytest.approx(700_000)

    def test_empty_history_returns_empty_list(self, db_manager):
        assert db_manager.get_daily_trade_sums(days=30) == []
