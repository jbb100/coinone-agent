#!/usr/bin/env python3
"""
KAIROS-1 Multi-Account Management System

여러 코인원 계정을 동시에 관리하는 통합 시스템
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# CLI 모듈 import 및 실행
from src.cli.multi_account_cli import multi_account

if __name__ == '__main__':
    print("""
🏦 KAIROS-1 멀티 계정 관리 시스템
==========================================
여러 코인원 계정을 동시에 관리하는 통합 투자 시스템

사용 가능한 명령어:
• accounts [-d]          - 계정 목록 조회 (상세: -d)
• add <계정ID> <이름> <API키> <시크릿키>  - 새 계정 추가
• remove <계정ID>        - 계정 제거
• portfolio [-a 계정ID]  - 포트폴리오 현황 조회
• rebalance [-a 계정ID]  - 리밸런싱 실행
• schedules              - 스케줄 현황
• health                 - 시스템 상태 확인

예시:
  python3 kairos1_multi.py accounts
  python3 kairos1_multi.py add acc1 "계정1" "api_key" "secret_key"
  python3 kairos1_multi.py portfolio -a acc1
  python3 kairos1_multi.py rebalance --force
==========================================
""")
    
    # CLI 실행
    multi_account()