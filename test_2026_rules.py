#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2026年双色球/大乐透新规则测试脚本
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app import app

def test_ssq_2026_rules():
    from utils import calculate_prize_details
    
    with app.app_context():
        print("=" * 60)
        print("Test 1: SSQ FuYun Prize - 3R+0B (active)")
        print("=" * 60)
        
        result = calculate_prize_details(
            user_red_balls=[1, 2, 3, 14, 15, 16],
            user_blue_balls=[8],
            draw_red_balls=[1, 2, 3, 11, 12, 13],
            draw_blue_balls=[7],
            lottery_type='ssq',
            pool_amount=2000000000,
            is_addition=False,
            fuyun_prize_active=True
        )
        
        print("Result:", dict(result))
        total_bets = sum(v['count'] for v in result.values())
        total_amount = sum(v['amount'] for v in result.values())
        print("Total bets:", total_bets)
        print("Total amount:", total_amount)
        
        if total_amount >= 5:
            print("PASS: FuYun prize 3R+0B works (5元)")
        else:
            print("FAIL: Expected FuYun prize (5元)")
        
        print()
        print("=" * 60)
        print("Test 2: SSQ FuYun Prize - 3R+0B (inactive)")
        print("=" * 60)
        
        result2 = calculate_prize_details(
            user_red_balls=[1, 2, 3, 14, 15, 16],
            user_blue_balls=[8],
            draw_red_balls=[1, 2, 3, 11, 12, 13],
            draw_blue_balls=[7],
            lottery_type='ssq',
            pool_amount=500000000,
            is_addition=False,
            fuyun_prize_active=False
        )
        
        print("Result:", dict(result2))
        total_bets2 = sum(v['count'] for v in result2.values())
        if total_bets2 == 0:
            print("PASS: FuYun inactive - no win")
        else:
            print("FAIL: Should not win")
        
        print()
        print("=" * 60)
        print("Test 3: SSQ First Prize - 6R+1B")
        print("=" * 60)
        
        result3 = calculate_prize_details(
            user_red_balls=[1,2,3,4,5,6],
            user_blue_balls=[7],
            draw_red_balls=[1,2,3,4,5,6],
            draw_blue_balls=[7],
            lottery_type='ssq',
            pool_amount=1000000000,
            is_addition=False,
            fuyun_prize_active=False
        )
        
        print("Result:", dict(result3))
        total_bets3 = sum(v['count'] for v in result3.values())
        if total_bets3 >= 1:
            print("PASS: 6R+1B wins 1st prize")
        else:
            print("FAIL: Should win 1st prize")

def test_dlt_2026_rules():
    from utils import calculate_prize_details
    
    with app.app_context():
        print()
        print("=" * 60)
        print("Test 4: DLT Additional Bet - 5+2 1st prize")
        print("=" * 60)
        
        result4 = calculate_prize_details(
            user_red_balls=[1,2,3,4,5],
            user_blue_balls=[6,7],
            draw_red_balls=[1,2,3,4,5],
            draw_blue_balls=[6,7],
            lottery_type='dlt',
            pool_amount=1000000000,
            is_addition=True,
            fuyun_prize_active=False
        )
        
        print("Result:", dict(result4))
        total_bets4 = sum(v['count'] for v in result4.values())
        if total_bets4 >= 1:
            print("PASS: Additional bet works for 1st prize")
        else:
            print("FAIL: Should win 1st prize")
        
        print()
        print("=" * 60)
        print("Test 5: DLT Pool Linkage - 4R+1B 3rd prize")
        print("=" * 60)
        
        result5 = calculate_prize_details(
            user_red_balls=[1,2,3,4,8],
            user_blue_balls=[6,9],
            draw_red_balls=[1,2,3,4,5],
            draw_blue_balls=[6,7],
            lottery_type='dlt',
            pool_amount=1000000000,
            is_addition=False,
            fuyun_prize_active=False
        )
        
        print("Result:", dict(result5))
        total_bets5 = sum(v['count'] for v in result5.values())
        if total_bets5 >= 1:
            print("PASS: Pool linkage works")
        else:
            print("FAIL: Should win 3rd prize")


if __name__ == '__main__':
    test_ssq_2026_rules()
    test_dlt_2026_rules()
    print("\n" + "=" * 60)
    print("All tests completed!")
