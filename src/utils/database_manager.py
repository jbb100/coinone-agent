"""
Database Manager

SQLite 데이터베이스 관리를 담당하는 모듈
"""

import os
import json
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from contextlib import contextmanager
from loguru import logger


def serialize_for_json(obj):
    """JSON 직렬화를 위한 헬퍼 함수"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    else:
        return obj


class DatabaseManager:
    """
    데이터베이스 관리자
    
    SQLite를 사용하여 시스템 데이터를 저장하고 관리합니다.
    """
    
    def __init__(self, config):
        """
        Args:
            config: ConfigLoader 인스턴스
        """
        self.config = config
        self.db_path = Path(config.get("database.sqlite_path", "./data/kairos1.db"))
        
        # 데이터베이스 디렉토리 생성
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 데이터베이스 초기화
        self._initialize_database()
        
        logger.info(f"DatabaseManager 초기화: {self.db_path}")
    
    @contextmanager
    def get_connection(self):
        """데이터베이스 연결 컨텍스트 매니저"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # 컬럼명으로 접근 가능
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"데이터베이스 오류: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def _initialize_database(self):
        """데이터베이스 테이블 초기화"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # TWAP 주문 테이블
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS twap_orders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        execution_id TEXT NOT NULL,
                        asset TEXT NOT NULL,
                        side TEXT NOT NULL,
                        total_amount_krw REAL NOT NULL,
                        total_quantity REAL NOT NULL,
                        slice_count INTEGER NOT NULL,
                        slice_amount_krw REAL NOT NULL,
                        slice_quantity REAL NOT NULL,
                        executed_slices INTEGER DEFAULT 0,
                        remaining_amount_krw REAL NOT NULL,
                        remaining_quantity REAL NOT NULL,
                        status TEXT NOT NULL,
                        start_time TEXT NOT NULL,
                        end_time TEXT NOT NULL,
                        last_execution_time TEXT,
                        market_season TEXT,
                        target_allocation TEXT,
                        exchange_order_ids TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # TWAP 실행 기록 테이블
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS twap_executions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        execution_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        start_time TEXT NOT NULL,
                        end_time TEXT,
                        market_season TEXT,
                        target_allocation TEXT,
                        twap_orders_detail TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        completed_at TEXT
                    )
                """)

                # 시장 분석 테이블
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS market_analysis (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        analysis_date TEXT NOT NULL,
                        market_season TEXT NOT NULL,
                        btc_price REAL,
                        ma_200w REAL,
                        price_ratio REAL,
                        allocation_crypto REAL,
                        allocation_krw REAL,
                        season_changed BOOLEAN,
                        analysis_data TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # 포트폴리오 스냅샷 테이블
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        snapshot_date TEXT NOT NULL,
                        total_value_krw REAL NOT NULL,
                        portfolio_detail TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # 거래 기록 테이블
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trade_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trade_date TEXT NOT NULL,
                        asset TEXT NOT NULL,
                        side TEXT NOT NULL,
                        price REAL NOT NULL,
                        quantity REAL NOT NULL,
                        amount_krw REAL NOT NULL,
                        fee_krw REAL,
                        order_id TEXT,
                        execution_id TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # 리밸런싱 결과 테이블
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS rebalance_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        success INTEGER NOT NULL DEFAULT 0,
                        orders_executed INTEGER DEFAULT 0,
                        orders_failed INTEGER DEFAULT 0,
                        total_value_before REAL,
                        total_value_after REAL,
                        market_season TEXT,
                        rebalance_data TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # 리밸런싱 히스토리 테이블 (save_rebalance_result 메서드용)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS rebalance_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        rebalance_date TEXT NOT NULL,
                        market_season TEXT,
                        success INTEGER NOT NULL DEFAULT 0,
                        total_value_before REAL,
                        total_value_after REAL,
                        value_change REAL,
                        orders_executed INTEGER DEFAULT 0,
                        orders_failed INTEGER DEFAULT 0,
                        rebalance_data TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 기존 테이블에 completed_at 컬럼이 없으면 추가
                try:
                    cursor.execute("ALTER TABLE twap_executions ADD COLUMN completed_at TEXT")
                    logger.info("twap_executions 테이블에 completed_at 컬럼 추가")
                except Exception as e:
                    # 컬럼이 이미 존재하는 경우 무시
                    if "duplicate column name" not in str(e).lower():
                        logger.debug(f"completed_at 컬럼 추가 시도 중 오류 (무시됨): {e}")
                
                conn.commit()
                logger.info("데이터베이스 테이블 초기화 완료")
                
        except Exception as e:
            logger.error(f"데이터베이스 초기화 실패: {e}")
            raise
    
    def save_market_analysis(self, analysis_result: Dict) -> int:
        """
        시장 분석 결과 저장
        
        Args:
            analysis_result: 분석 결과 딕셔너리
            
        Returns:
            저장된 레코드 ID
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                analysis_info = analysis_result.get("analysis_info", {})
                allocation_weights = analysis_result.get("allocation_weights", {})
                
                cursor.execute("""
                    INSERT INTO market_analysis (
                        analysis_date, market_season, btc_price, ma_200w, price_ratio,
                        allocation_crypto, allocation_krw, season_changed, analysis_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    analysis_result.get("analysis_date", datetime.now()),
                    analysis_result.get("market_season"),
                    analysis_info.get("current_price"),
                    analysis_info.get("ma_200w"),
                    analysis_info.get("price_ratio"),
                    allocation_weights.get("crypto"),
                    allocation_weights.get("krw"),
                    analysis_result.get("season_changed", False),
                    json.dumps(serialize_for_json(analysis_result))
                ))
                
                record_id = cursor.lastrowid
                conn.commit()
                
                logger.info(f"시장 분석 결과 저장 완료: ID {record_id}")
                return record_id
                
        except Exception as e:
            logger.error(f"시장 분석 결과 저장 실패: {e}")
            raise
    
    def get_latest_market_analysis(self) -> Optional[Dict]:
        """
        최근 시장 분석 결과 조회
        
        Returns:
            최근 분석 결과 또는 None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM market_analysis 
                    ORDER BY analysis_date DESC 
                    LIMIT 1
                """)
                
                row = cursor.fetchone()
                if row:
                    result = dict(row)
                    # JSON 데이터 파싱
                    if result["analysis_data"]:
                        analysis_data = json.loads(result["analysis_data"])
                        result.update(analysis_data)
                    
                    return result
                
                return None
                
        except Exception as e:
            logger.error(f"최근 시장 분석 결과 조회 실패: {e}")
            return None
    
    def save_rebalance_result(self, rebalance_result: Dict) -> int:
        """
        리밸런싱 결과 저장
        
        Args:
            rebalance_result: 리밸런싱 결과
            
        Returns:
            저장된 레코드 ID
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                summary = rebalance_result.get("rebalance_summary", {})
                
                cursor.execute("""
                    INSERT INTO rebalance_history (
                        rebalance_date, market_season, success, total_value_before,
                        total_value_after, value_change, orders_executed, orders_failed,
                        rebalance_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rebalance_result.get("timestamp", datetime.now()),
                    summary.get("market_season"),
                    rebalance_result.get("success", False),
                    rebalance_result.get("total_value_before"),
                    rebalance_result.get("total_value_after"),
                    summary.get("value_change"),
                    len(rebalance_result.get("executed_orders", [])),
                    len(rebalance_result.get("failed_orders", [])),
                    json.dumps(serialize_for_json(rebalance_result))
                ))
                
                record_id = cursor.lastrowid
                conn.commit()
                
                logger.info(f"리밸런싱 결과 저장 완료: ID {record_id}")
                return record_id
                
        except Exception as e:
            logger.error(f"리밸런싱 결과 저장 실패: {e}")
            raise
    
    def save_trade(self, trade_info: Dict) -> int:
        """
        거래 내역 저장
        
        Args:
            trade_info: 거래 정보
            
        Returns:
            저장된 레코드 ID
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO trade_history (
                        order_id, currency, side, order_type, amount, price,
                        filled_amount, average_price, fee, status, trade_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_info.get("order_id"),
                    trade_info.get("currency"),
                    trade_info.get("side"),
                    trade_info.get("order_type"),
                    trade_info.get("amount"),
                    trade_info.get("price"),
                    trade_info.get("filled_amount", 0),
                    trade_info.get("average_price", 0),
                    trade_info.get("fee", 0),
                    trade_info.get("status"),
                    trade_info.get("created_at", datetime.now())
                ))
                
                record_id = cursor.lastrowid
                conn.commit()
                
                return record_id
                
        except Exception as e:
            logger.error(f"거래 내역 저장 실패: {e}")
            raise
    
    def save_portfolio_snapshot(self, portfolio_data: Dict) -> int:
        """
        포트폴리오 스냅샷 저장
        
        Args:
            portfolio_data: 포트폴리오 데이터
            
        Returns:
            저장된 레코드 ID
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                assets = portfolio_data.get("assets", {})
                
                # 각 자산의 정보 추출
                def get_asset_info(asset_name):
                    asset_data = assets.get(asset_name, {})
                    if isinstance(asset_data, dict):
                        return asset_data.get("balance", 0), asset_data.get("value_krw", 0)
                    else:
                        return asset_data, 0
                
                btc_balance, btc_value = get_asset_info("BTC")
                eth_balance, eth_value = get_asset_info("ETH")
                xrp_balance, xrp_value = get_asset_info("XRP")
                sol_balance, sol_value = get_asset_info("SOL")
                krw_balance = assets.get("KRW", 0)
                
                cursor.execute("""
                    INSERT INTO portfolio_snapshots (
                        snapshot_date, total_value_krw, krw_balance,
                        btc_balance, btc_value_krw, eth_balance, eth_value_krw,
                        xrp_balance, xrp_value_krw, sol_balance, sol_value_krw,
                        portfolio_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now(),
                    portfolio_data.get("total_krw", 0),
                    krw_balance,
                    btc_balance, btc_value,
                    eth_balance, eth_value,
                    xrp_balance, xrp_value,
                    sol_balance, sol_value,
                    json.dumps(serialize_for_json(portfolio_data))
                ))
                
                record_id = cursor.lastrowid
                conn.commit()
                
                return record_id
                
        except Exception as e:
            logger.error(f"포트폴리오 스냅샷 저장 실패: {e}")
            raise
    
    def get_portfolio_history(self, days: int = 30) -> List[Dict]:
        """
        포트폴리오 이력 조회
        
        Args:
            days: 조회 기간 (일)
            
        Returns:
            포트폴리오 이력 리스트
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cutoff_date = datetime.now() - timedelta(days=days)
                
                cursor.execute("""
                    SELECT * FROM portfolio_snapshots 
                    WHERE snapshot_date >= ?
                    ORDER BY snapshot_date ASC
                """, (cutoff_date,))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"포트폴리오 이력 조회 실패: {e}")
            return []
    
    def get_trade_history(self, days: int = 30) -> List[Dict]:
        """
        거래 내역 조회
        
        Args:
            days: 조회 기간 (일)
            
        Returns:
            거래 내역 리스트
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cutoff_date = datetime.now() - timedelta(days=days)
                
                cursor.execute("""
                    SELECT * FROM trade_history 
                    WHERE trade_date >= ?
                    ORDER BY trade_date DESC
                """, (cutoff_date,))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"거래 내역 조회 실패: {e}")
            return []
    
    def get_rebalance_history(self, limit: int = 10) -> List[Dict]:
        """
        리밸런싱 이력 조회
        
        Args:
            limit: 조회할 최대 건수
            
        Returns:
            리밸런싱 이력 리스트
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM rebalance_history 
                    ORDER BY rebalance_date DESC 
                    LIMIT ?
                """, (limit,))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"리밸런싱 이력 조회 실패: {e}")
            return []
    
    def cleanup_old_data(self, retention_days: int = 365):
        """
        오래된 데이터 정리
        
        Args:
            retention_days: 보관 기간 (일)
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cutoff_date = datetime.now() - timedelta(days=retention_days)
                
                # 오래된 포트폴리오 스냅샷 삭제 (월말 데이터 제외)
                cursor.execute("""
                    DELETE FROM portfolio_snapshots 
                    WHERE snapshot_date < ? 
                    AND strftime('%d', snapshot_date) != '01'
                """, (cutoff_date,))
                
                # 오래된 거래 내역 삭제
                cursor.execute("""
                    DELETE FROM trade_history 
                    WHERE trade_date < ?
                """, (cutoff_date,))
                
                conn.commit()
                logger.info(f"오래된 데이터 정리 완료: {retention_days}일 이전")
                
        except Exception as e:
            logger.error(f"데이터 정리 실패: {e}")
    
    def backup_database(self, backup_path: Optional[str] = None) -> str:
        """
        데이터베이스 백업
        
        Args:
            backup_path: 백업 파일 경로 (선택사항)
            
        Returns:
            백업 파일 경로
        """
        try:
            if backup_path is None:
                backup_dir = Path(self.config.get("database.backup.backup_path", "./backups"))
                backup_dir.mkdir(parents=True, exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = backup_dir / f"kairos1_backup_{timestamp}.db"
            
            # SQLite 백업 수행
            with self.get_connection() as source_conn:
                backup_conn = sqlite3.connect(backup_path)
                source_conn.backup(backup_conn)
                backup_conn.close()
            
            logger.info(f"데이터베이스 백업 완료: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"데이터베이스 백업 실패: {e}")
            raise
    
    def save_twap_execution_plan(self, execution_id: str, twap_orders: List[Any]) -> None:
        """
        TWAP 실행 계획을 데이터베이스에 저장
        
        Args:
            execution_id: 실행 ID
            twap_orders: TWAP 주문 리스트
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 1. 실행 계획 저장
                cursor.execute("""
                    INSERT INTO twap_executions (
                        execution_id,
                        start_time,
                        status
                    ) VALUES (?, ?, ?)
                """, (
                    execution_id,
                    datetime.now().isoformat(),
                    "executing"
                ))
                
                # 2. TWAP 주문 상세 정보 저장
                twap_orders_detail = [
                    {
                        "asset": order.asset,
                        "side": order.side,
                        "total_amount_krw": order.total_amount_krw,
                        "total_quantity": order.total_quantity,
                        "execution_hours": order.execution_hours,
                        "slice_count": order.slice_count,
                        "slice_amount_krw": order.slice_amount_krw,
                        "slice_quantity": order.slice_quantity,
                        "start_time": order.start_time.isoformat(),
                        "end_time": order.end_time.isoformat(),
                        "slice_interval_minutes": order.slice_interval_minutes,
                        "executed_slices": order.executed_slices,
                        "remaining_amount_krw": order.remaining_amount_krw,
                        "remaining_quantity": order.remaining_quantity,
                        "status": order.status,
                        "last_execution_time": order.last_execution_time.isoformat() if order.last_execution_time else None,
                        "market_season": order.market_season,
                        "target_allocation": order.target_allocation,
                        "created_at": order.created_at.isoformat(),
                        "exchange_order_ids": order.exchange_order_ids,
                        "last_rebalance_check": order.last_rebalance_check.isoformat() if order.last_rebalance_check else None
                    } for order in twap_orders
                ]
                
                cursor.execute("""
                    UPDATE twap_executions 
                    SET twap_orders_detail = ?
                    WHERE execution_id = ?
                """, (json.dumps(twap_orders_detail), execution_id))
                
                conn.commit()
                logger.info(f"TWAP 실행 계획 저장 완료: {execution_id} ({len(twap_orders)}개 주문)")
                
        except Exception as e:
            logger.error(f"TWAP 실행 계획 저장 실패: {e}")
            raise

    def update_twap_orders_status(self, execution_id: str, orders: List[Dict]):
        """TWAP 주문 상태 업데이트"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                for order in orders:
                    # exchange_order_ids와 target_allocation을 JSON으로 변환
                    exchange_order_ids = json.dumps(order.get('exchange_order_ids', []))
                    target_allocation = json.dumps(order.get('target_allocation', {}))
                    
                    # datetime 객체를 ISO 형식 문자열로 변환
                    last_execution_time = order.get('last_execution_time')
                    if last_execution_time and isinstance(last_execution_time, datetime):
                        last_execution_time = last_execution_time.isoformat()
                    
                    cursor.execute("""
                        UPDATE twap_orders SET
                            executed_slices = ?,
                            remaining_amount_krw = ?,
                            remaining_quantity = ?,
                            status = ?,
                            last_execution_time = ?,
                            exchange_order_ids = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE execution_id = ? AND asset = ?
                    """, (
                        order['executed_slices'],
                        order['remaining_amount_krw'],
                        order['remaining_quantity'],
                        order['status'],
                        last_execution_time,
                        exchange_order_ids,
                        execution_id,
                        order['asset']
                    ))
                
                conn.commit()
                logger.debug(f"TWAP 주문 상태 업데이트 완료: {len(orders)}개")
                
        except Exception as e:
            logger.error(f"TWAP 주문 상태 업데이트 실패: {e}")
            raise

    def load_active_twap_orders(self, execution_id: str) -> List[Dict]:
        """활성 TWAP 주문 로드"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM twap_orders 
                    WHERE execution_id = ? 
                    AND status IN ('pending', 'executing')
                    ORDER BY created_at ASC
                """, (execution_id,))
                
                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                
                orders = []
                for row in rows:
                    order_dict = dict(zip(columns, row))
                    # JSON 문자열을 딕셔너리로 변환
                    if order_dict.get('target_allocation'):
                        order_dict['target_allocation'] = json.loads(order_dict['target_allocation'])
                    if order_dict.get('exchange_order_ids'):
                        order_dict['exchange_order_ids'] = json.loads(order_dict['exchange_order_ids'])
                    else:
                        order_dict['exchange_order_ids'] = []
                    
                    # 날짜/시간 문자열을 datetime 객체로 변환
                    for field in ['start_time', 'end_time', 'last_execution_time', 'created_at']:
                        if order_dict.get(field):
                            order_dict[field] = datetime.fromisoformat(order_dict[field])
                    
                    orders.append(order_dict)
                
                return orders
                
        except Exception as e:
            logger.error(f"활성 TWAP 주문 로드 실패: {e}")
            return []

    def update_twap_execution_status(self, execution_id: int, status: str, result_data: dict = None):
        """
        TWAP 실행 상태 업데이트 (호환성을 위한 메서드)
        
        Args:
            execution_id: 실행 ID
            status: 상태 (active, completed, failed)
            result_data: 결과 데이터
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if result_data:
                    cursor.execute("""
                        UPDATE twap_executions 
                        SET status = ?, result_data = ?, completed_at = ?
                        WHERE id = ?
                    """, (
                        status,
                        json.dumps(serialize_for_json(result_data)),
                        datetime.now().isoformat(),
                        execution_id
                    ))
                else:
                    cursor.execute("""
                        UPDATE twap_executions 
                        SET status = ?
                        WHERE id = ?
                    """, (status, execution_id))
                
                conn.commit()
                logger.info(f"TWAP 실행 상태 업데이트 완료: ID {execution_id} → {status}")
            
        except Exception as e:
            logger.error(f"TWAP 실행 상태 업데이트 실패: {e}")

    def get_active_twap_executions(self) -> List[dict]:
        """
        활성 TWAP 실행 목록 조회 (호환성을 위한 메서드)
        
        Returns:
            활성 TWAP 실행 리스트
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, start_time, execution_plan, status, created_at
                    FROM twap_executions 
                    WHERE status = 'active'
                    ORDER BY created_at DESC
                """)
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        "id": row[0],
                        "start_time": row[1],
                        "execution_plan": json.loads(row[2]),
                        "status": row[3],
                        "created_at": row[4]
                    })
                
                return results
            
        except Exception as e:
            logger.error(f"활성 TWAP 실행 조회 실패: {e}")
            return []

    def get_latest_active_twap_execution(self) -> Optional[Dict]:
        """
        가장 최근의 활성 TWAP 실행 계획을 조회
        
        Returns:
            활성 TWAP 실행 정보 또는 None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT execution_id, twap_orders_detail
                    FROM twap_executions
                    WHERE status = 'executing'
                    ORDER BY start_time DESC
                    LIMIT 1
                """)
                row = cursor.fetchone()
                if row:
                    return {
                        "execution_id": row["execution_id"],
                        "twap_orders_detail": json.loads(row["twap_orders_detail"])
                    }
                return None
        except Exception as e:
            logger.error(f"최신 활성 TWAP 실행 조회 실패: {e}")
            return None

    def update_twap_execution_plan(self, execution_id: str, twap_orders: List[Dict]) -> None:
        """TWAP 실행 계획의 주문 상세 정보를 업데이트 (진행 상황 저장)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # TWAPOrder 객체는 dataclasses.asdict를 사용하거나 to_dict 메서드를 구현해야 함
                twap_orders_detail_json = json.dumps([serialize_for_json(o) for o in twap_orders])
                
                cursor.execute("""
                    UPDATE twap_executions 
                    SET twap_orders_detail = ?
                    WHERE execution_id = ?
                """, (twap_orders_detail_json, execution_id))
                
                conn.commit()
                logger.info(f"TWAP 실행 계획 업데이트 완료: {execution_id}")
        except Exception as e:
            logger.error(f"TWAP 실행 계획 업데이트 실패: {e}")
            raise
    
    def get_latest_rebalance_record(self) -> Optional[Dict]:
        """
        가장 최근 리밸런싱 기록 조회
        
        Returns:
            최근 리밸런싱 기록 또는 None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 먼저 rebalance_results 테이블에서 조회
                cursor.execute("""
                    SELECT timestamp, success, orders_executed, total_value_before, total_value_after
                    FROM rebalance_results 
                    WHERE success = 1
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """)
                
                row = cursor.fetchone()
                if row:
                    return {
                        "timestamp": row["timestamp"],
                        "success": bool(row["success"]),
                        "orders_executed": row["orders_executed"],
                        "total_value_before": row["total_value_before"],
                        "total_value_after": row["total_value_after"]
                    }
                
                # rebalance_results가 없으면 twap_executions에서 완료된 것 조회
                cursor.execute("""
                    SELECT start_time, completed_at, status
                    FROM twap_executions 
                    WHERE status = 'completed'
                    ORDER BY completed_at DESC 
                    LIMIT 1
                """)
                
                row = cursor.fetchone()
                if row:
                    return {
                        "timestamp": row["completed_at"] or row["start_time"],
                        "success": True,
                        "type": "twap_rebalance"
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"최근 리밸런싱 기록 조회 실패: {e}")
            return None
    
    def save_opportunistic_buy_record(self, record: Dict):
        """기회적 매수 기록 저장"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 테이블이 없으면 생성
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS opportunistic_buys (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        asset TEXT NOT NULL,
                        amount_krw REAL NOT NULL,
                        price REAL NOT NULL,
                        opportunity_level TEXT,
                        price_drop_7d REAL,
                        price_drop_30d REAL,
                        rsi REAL,
                        fear_greed_index REAL,
                        confidence_score REAL,
                        order_id TEXT,
                        status TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 기록 저장
                cursor.execute("""
                    INSERT INTO opportunistic_buys (
                        timestamp, asset, amount_krw, price, opportunity_level,
                        price_drop_7d, price_drop_30d, rsi, fear_greed_index,
                        confidence_score, order_id, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record["timestamp"].isoformat(),
                    record["asset"],
                    record["amount_krw"],
                    record["price"],
                    record.get("opportunity_level"),
                    record.get("price_drop_7d"),
                    record.get("price_drop_30d"),
                    record.get("rsi"),
                    record.get("fear_greed_index"),
                    record.get("confidence_score"),
                    record.get("order_id"),
                    record.get("status", "executed")
                ))
                
                conn.commit()
                logger.info(f"기회적 매수 기록 저장 완료: {record['asset']} - {record['amount_krw']:,.0f} KRW")
                
        except Exception as e:
            logger.error(f"기회적 매수 기록 저장 실패: {e}")
    
    def get_market_data(self, asset: str, days: int = 30) -> pd.DataFrame:
        """
        시장 데이터 조회 (가격 데이터)
        
        Args:
            asset: 자산 심볼 (BTC, ETH 등)
            days: 조회 기간 (일)
            
        Returns:
            pandas DataFrame with columns: Close, High, Low, Open, Volume
            빈 DataFrame 반환 시 실제 가격 데이터가 없음을 의미
        """
        try:
            import yfinance as yf
            from datetime import datetime, timedelta
            
            # Yahoo Finance 심볼 매핑
            symbol_map = {
                'BTC': 'BTC-USD',
                'ETH': 'ETH-USD',
                'XRP': 'XRP-USD',
                'SOL': 'SOL-USD',
                'ADA': 'ADA-USD',
                'DOT': 'DOT-USD',
                'MATIC': 'MATIC-USD'
            }
            
            yahoo_symbol = symbol_map.get(asset.upper())
            if not yahoo_symbol:
                logger.warning(f"get_market_data: {asset} 심볼을 찾을 수 없습니다.")
                return pd.DataFrame(columns=['Close', 'High', 'Low', 'Open', 'Volume'])
            
            # 실시간 데이터 가져오기 시도
            try:
                ticker = yf.Ticker(yahoo_symbol)
                period_str = f"{days}d"
                price_data = ticker.history(period=period_str)
                
                if not price_data.empty:
                    # 컬럼명 통일 (Yahoo Finance는 대문자 사용)
                    price_data = price_data.rename(columns={
                        'Open': 'Open',
                        'High': 'High', 
                        'Low': 'Low',
                        'Close': 'Close',
                        'Volume': 'Volume'
                    })
                    
                    # 필요한 컬럼만 선택
                    price_data = price_data[['Open', 'High', 'Low', 'Close', 'Volume']]
                    
                    logger.info(f"get_market_data: {asset}의 {len(price_data)}일 실시간 데이터 조회 완료")
                    return price_data
                    
            except Exception as api_error:
                logger.warning(f"실시간 데이터 조회 실패 ({asset}): {api_error}")
            
            # 실시간 데이터 실패 시 빈 DataFrame 반환
            logger.warning(f"get_market_data: {asset}의 {days}일 시장 데이터를 가져올 수 없습니다. 빈 DataFrame을 반환합니다.")
            return pd.DataFrame(columns=['Close', 'High', 'Low', 'Open', 'Volume'])
            
        except Exception as e:
            logger.error(f"시장 데이터 조회 실패: {asset}, {days}일 - {e}")
            return pd.DataFrame(columns=['Close', 'High', 'Low', 'Open', 'Volume']) 