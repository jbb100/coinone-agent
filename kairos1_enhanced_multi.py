#!/usr/bin/env python3
"""
KAIROS-1 Enhanced Multi-Account Management System

모든 기능을 멀티 계정에서 동일하게 제공하는 확장된 통합 시스템
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Enhanced CLI 모듈 import 및 실행
from src.cli.enhanced_multi_account_cli import enhanced_multi_account

if __name__ == '__main__':
    print("""
🚀 KAIROS-1 Enhanced Multi-Account System
=========================================
모든 기능을 멀티 계정에서 동일하게 제공하는 통합 투자 시스템

🏦 계정 관리:
• accounts [-d]                    - 계정 목록 조회 (상세: -d)

📊 포트폴리오 관리:
• optimize [-a 계정ID]             - 포트폴리오 최적화 실행
• rebalance [-a 계정ID] [--live]   - 리밸런싱 실행 (실제거래: --live)

📈 분석 기능:
• risk [-a 계정ID]                 - 리스크 분석
• performance [-a 계정ID]          - 성과 분석  
• analytics                        - 통합 분석 정보

💡 전략 실행:
• dca [-a 계정ID] [--amount 금액]  - DCA+ 전략 실행
• tax [-a 계정ID]                  - 세금 최적화 분석

🎬 시스템 관리:
• status                           - 코디네이터 상태
• health                           - 시스템 헬스체크
• schedule <작업명> [-a 계정ID]     - 작업 스케줄링

📝 지원 작업명:
• portfolio_optimization           - 포트폴리오 최적화
• rebalancing                      - 리밸런싱
• risk_analysis                    - 리스크 분석
• performance_analysis             - 성과 분석
• dca_strategy                     - DCA+ 전략
• tax_optimization                 - 세금 최적화

사용 예시:
  python3 kairos1_enhanced_multi.py accounts -d
  python3 kairos1_enhanced_multi.py optimize -a main
  python3 kairos1_enhanced_multi.py rebalance --live
  python3 kairos1_enhanced_multi.py risk -a account1
  python3 kairos1_enhanced_multi.py analytics
  python3 kairos1_enhanced_multi.py schedule portfolio_optimization -p high
  python3 kairos1_enhanced_multi.py health

📋 특징:
✅ 모든 단일 계정 기능을 멀티 계정에서 제공
✅ 병렬 처리로 효율적인 멀티 계정 관리  
✅ 자동 스케줄링 및 우선순위 관리
✅ 통합 분석 및 리포팅
✅ 실시간 헬스체크 및 모니터링
=========================================
""")
    
    # Enhanced CLI 실행
    enhanced_multi_account()