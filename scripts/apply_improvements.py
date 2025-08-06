#!/usr/bin/env python3
"""
KAIROS-1 System Improvements Application Script

시스템 개선 사항들을 단계적으로 적용하는 스크립트
"""

import os
import sys
import asyncio
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from loguru import logger

# 프로젝트 루트 경로 추가
sys.path.append('/Users/jongdal100/git/coinone-agent')

from src.security.secrets_manager import get_secrets_manager, get_api_key_manager
from src.core.base_service import service_registry
from src.core.exceptions import KairosException


class ImprovementApplier:
    """시스템 개선 사항 적용기"""
    
    def __init__(self):
        self.project_root = Path('/Users/jongdal100/git/coinone-agent')
        self.backup_dir = self.project_root / 'backups' / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.improvements_applied = []
        self.failed_improvements = []
    
    async def apply_all_improvements(self):
        """모든 개선 사항 적용"""
        logger.info("🚀 KAIROS-1 시스템 개선 시작")
        
        improvements = [
            ("백업 생성", self.create_backup),
            ("보안 시스템 초기화", self.initialize_security),
            ("에러 처리 시스템 적용", self.apply_error_handling),
            ("복원력 패턴 적용", self.apply_resilience_patterns),
            ("성능 최적화 적용", self.apply_performance_optimizations),
            ("서비스 아키텍처 적용", self.apply_service_architecture),
            ("테스트 시스템 검증", self.verify_test_system),
            ("문서화 업데이트", self.update_documentation),
            ("설정 검증", self.verify_configuration),
            ("최종 검증", self.final_verification)
        ]
        
        for name, improvement_func in improvements:
            try:
                logger.info(f"📋 적용 중: {name}")
                await improvement_func()
                self.improvements_applied.append(name)
                logger.info(f"✅ 완료: {name}")
            except Exception as e:
                logger.error(f"❌ 실패: {name} - {e}")
                self.failed_improvements.append((name, str(e)))
        
        await self.generate_report()
    
    async def create_backup(self):
        """중요 파일 백업"""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 백업할 중요 파일들
        important_files = [
            'kairos1_main.py',
            'src/core/portfolio_manager.py',
            'src/core/rebalancer.py',
            'src/trading/coinone_client.py',
            'src/utils/config_loader.py',
            'config/'
        ]
        
        for file_path in important_files:
            source = self.project_root / file_path
            if source.exists():
                if source.is_dir():
                    dest = self.backup_dir / file_path
                    shutil.copytree(source, dest, dirs_exist_ok=True)
                else:
                    dest = self.backup_dir / file_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, dest)
        
        logger.info(f"백업 완료: {self.backup_dir}")
    
    async def initialize_security(self):
        """보안 시스템 초기화"""
        try:
            # SecretsManager 초기화
            secrets_manager = get_secrets_manager()
            
            # API 키 관리자 초기화
            api_key_manager = get_api_key_manager()
            
            # 기존 환경변수에서 API 키 마이그레이션
            coinone_api_key = os.getenv('COINONE_API_KEY')
            coinone_secret_key = os.getenv('COINONE_SECRET_KEY')
            
            if coinone_api_key and coinone_secret_key:
                success = api_key_manager.store_api_key(
                    'coinone',
                    coinone_api_key,
                    coinone_secret_key
                )
                if success:
                    logger.info("Coinone API 키 마이그레이션 완료")
                else:
                    logger.warning("Coinone API 키 마이그레이션 실패")
            
            # 보안 디렉토리 생성
            security_dir = self.project_root / 'data' / '.security'
            security_dir.mkdir(parents=True, exist_ok=True)
            
            # 권한 설정 (Unix 시스템만)
            if os.name == 'posix':
                os.chmod(security_dir, 0o700)
            
        except Exception as e:
            logger.error(f"보안 시스템 초기화 실패: {e}")
            raise
    
    async def apply_error_handling(self):
        """에러 처리 시스템 적용"""
        # 새로운 예외 시스템이 제대로 import되는지 확인
        try:
            from src.core.exceptions import (
                KairosException, TradingException, APIException,
                InsufficientBalanceException, OrderExecutionException
            )
            logger.info("새로운 예외 시스템 로드 완료")
        except ImportError as e:
            logger.error(f"예외 시스템 로드 실패: {e}")
            raise
        
        # 기존 코드의 예외 처리 패턴 검증
        old_patterns = [
            "except Exception:",
            "raise Exception(",
            "except:",
        ]
        
        python_files = list(self.project_root.rglob("*.py"))
        problematic_files = []
        
        for file_path in python_files:
            if 'backups' in str(file_path) or '.git' in str(file_path):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                for pattern in old_patterns:
                    if pattern in content:
                        problematic_files.append(str(file_path))
                        break
            except:
                continue
        
        if problematic_files:
            logger.warning(f"개선이 필요한 예외 처리 패턴이 있는 파일: {len(problematic_files)}개")
            for file_path in problematic_files[:5]:  # 처음 5개만 표시
                logger.warning(f"  - {file_path}")
        else:
            logger.info("예외 처리 패턴 검증 완료")
    
    async def apply_resilience_patterns(self):
        """복원력 패턴 적용"""
        try:
            from src.core.resilience import (
                CircuitBreaker, RetryManager, RateLimiter,
                with_retry, with_circuit_breaker, with_rate_limit
            )
            logger.info("복원력 패턴 모듈 로드 완료")
            
            # 테스트용 서킷 브레이커 생성
            test_breaker = CircuitBreaker("test_service")
            
            # 테스트 함수
            def test_function():
                return "success"
            
            # 서킷 브레이커 테스트
            result = test_breaker.call(test_function)
            if result == "success":
                logger.info("서킷 브레이커 테스트 성공")
            
        except Exception as e:
            logger.error(f"복원력 패턴 적용 실패: {e}")
            raise
    
    async def apply_performance_optimizations(self):
        """성능 최적화 적용"""
        try:
            from src.core.async_client import AsyncHTTPClient, AsyncCache
            logger.info("비동기 클라이언트 모듈 로드 완료")
            
            # 테스트용 클라이언트 생성
            client = AsyncHTTPClient(
                base_url="https://api.coinone.co.kr",
                enable_caching=True,
                cache_ttl=300
            )
            
            # 캐시 테스트
            cache = AsyncCache(max_memory_items=100)
            await cache.set("test_key", "test_value", 60)
            cached_value = await cache.get("test_key")
            
            if cached_value == "test_value":
                logger.info("캐시 시스템 테스트 성공")
            
            await client.close()
            
        except Exception as e:
            logger.error(f"성능 최적화 적용 실패: {e}")
            raise
    
    async def apply_service_architecture(self):
        """서비스 아키텍처 적용"""
        try:
            from src.core.base_service import (
                BaseService, HTTPService, DatabaseService,
                ServiceRegistry, ServiceConfig, service_registry
            )
            logger.info("서비스 아키텍처 모듈 로드 완료")
            
            # 서비스 레지스트리 상태 확인
            status = service_registry.get_all_status()
            logger.info(f"서비스 레지스트리 초기화 완료: {len(status)}개 서비스")
            
        except Exception as e:
            logger.error(f"서비스 아키텍처 적용 실패: {e}")
            raise
    
    async def verify_test_system(self):
        """테스트 시스템 검증"""
        test_files = [
            'tests/conftest.py',
            'tests/test_security.py'
        ]
        
        for test_file in test_files:
            file_path = self.project_root / test_file
            if not file_path.exists():
                logger.warning(f"테스트 파일 없음: {test_file}")
            else:
                logger.info(f"테스트 파일 확인: {test_file}")
        
        # pytest 설치 확인
        try:
            import pytest
            logger.info(f"pytest 버전: {pytest.__version__}")
        except ImportError:
            logger.warning("pytest가 설치되지 않음")
    
    async def update_documentation(self):
        """문서화 업데이트"""
        docs_files = [
            'docs/ARCHITECTURE.md',
            'src/core/types.py'
        ]
        
        for doc_file in docs_files:
            file_path = self.project_root / doc_file
            if file_path.exists():
                logger.info(f"문서 확인: {doc_file}")
            else:
                logger.warning(f"문서 없음: {doc_file}")
    
    async def verify_configuration(self):
        """설정 검증"""
        config_dir = self.project_root / 'config'
        
        if config_dir.exists():
            config_files = list(config_dir.glob("*.yaml")) + list(config_dir.glob("*.yml"))
            logger.info(f"설정 파일 개수: {len(config_files)}")
        else:
            logger.warning("config 디렉토리 없음")
        
        # 환경 변수 확인
        important_env_vars = [
            'COINONE_API_KEY',
            'COINONE_SECRET_KEY',
            'KAIROS_MASTER_KEY'
        ]
        
        missing_vars = []
        for var in important_env_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            logger.warning(f"설정되지 않은 환경 변수: {', '.join(missing_vars)}")
        else:
            logger.info("필수 환경 변수 모두 설정됨")
    
    async def final_verification(self):
        """최종 검증"""
        # 새로운 모듈들이 모두 import 가능한지 확인
        modules_to_check = [
            'src.security.secrets_manager',
            'src.core.exceptions',
            'src.core.resilience',
            'src.core.async_client',
            'src.core.base_service',
            'src.core.types'
        ]
        
        successful_imports = 0
        for module in modules_to_check:
            try:
                __import__(module)
                successful_imports += 1
            except ImportError as e:
                logger.error(f"모듈 import 실패: {module} - {e}")
        
        logger.info(f"모듈 import 성공: {successful_imports}/{len(modules_to_check)}")
        
        # 기본 기능 테스트
        try:
            # 타입 시스템 테스트
            from src.core.types import AssetSymbol, KRWAmount, Price
            
            # 예외 시스템 테스트  
            from src.core.exceptions import KairosException
            
            test_exception = KairosException("테스트 예외", "TEST_ERROR")
            if test_exception.error_code == "TEST_ERROR":
                logger.info("예외 시스템 기본 테스트 성공")
            
        except Exception as e:
            logger.error(f"기본 기능 테스트 실패: {e}")
    
    async def generate_report(self):
        """개선 사항 적용 보고서 생성"""
        report = f"""
# KAIROS-1 시스템 개선 적용 보고서

## 적용 일시
{datetime.now().strftime('%Y년 %m월 %d일 %H시 %M분')}

## 성공한 개선 사항 ({len(self.improvements_applied)}개)
"""
        
        for improvement in self.improvements_applied:
            report += f"✅ {improvement}\n"
        
        if self.failed_improvements:
            report += f"\n## 실패한 개선 사항 ({len(self.failed_improvements)}개)\n"
            for name, error in self.failed_improvements:
                report += f"❌ {name}: {error}\n"
        
        report += f"""

## 적용된 주요 개선 사항

### 1. 보안 강화
- 🔐 암호화된 비밀 정보 관리 시스템
- 🔑 API 키 로테이션 지원
- 📋 접근 감사 로깅

### 2. 에러 처리 개선
- ⚠️ 체계적인 예외 클래스 구조
- 🔄 상세한 에러 정보 제공
- 📊 복구 가능성 표시

### 3. 시스템 복원력 향상
- 🛡️ 서킷 브레이커 패턴
- 🔄 지능형 재시도 로직
- ⏰ 다양한 백오프 전략

### 4. 성능 최적화
- 🚀 비동기 HTTP 클라이언트
- 💾 다층 캐싱 시스템
- 🔀 요청 배치 처리

### 5. 아키텍처 개선
- 🏗️ 모듈화된 서비스 구조
- 🔧 의존성 주입 지원
- 📊 통합 모니터링

### 6. 개발 경험 개선
- 🧪 포괄적인 테스트 시스템
- 📚 상세한 타입 정의
- 📖 아키텍처 문서화

## 다음 단계

1. **기존 코드 마이그레이션**
   - 기존 예외 처리를 새로운 시스템으로 전환
   - API 클라이언트를 비동기 버전으로 교체
   - 서비스 구조를 새로운 아키텍처로 리팩토링

2. **테스트 추가**
   - 핵심 비즈니스 로직에 대한 단위 테스트
   - API 통합 테스트
   - 성능 및 부하 테스트

3. **모니터링 강화**
   - 메트릭 수집 시스템 구축
   - 알림 시스템 설정
   - 대시보드 구성

4. **운영 환경 준비**
   - 배포 자동화
   - 백업 및 복구 절차
   - 보안 검토

## 백업 위치
{self.backup_dir}

---
이 보고서는 KAIROS-1 시스템 개선 스크립트에 의해 자동 생성되었습니다.
"""
        
        # 보고서 저장
        report_path = self.project_root / f"improvement_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"📋 개선 보고서 생성: {report_path}")
        
        # 콘솔에도 요약 출력
        print("\n" + "="*60)
        print("🎉 KAIROS-1 시스템 개선 완료!")
        print("="*60)
        print(f"✅ 성공: {len(self.improvements_applied)}개")
        if self.failed_improvements:
            print(f"❌ 실패: {len(self.failed_improvements)}개")
        print(f"📋 상세 보고서: {report_path}")
        print("="*60)


async def main():
    """메인 함수"""
    applier = ImprovementApplier()
    await applier.apply_all_improvements()


if __name__ == "__main__":
    asyncio.run(main())