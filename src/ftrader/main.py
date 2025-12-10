"""主程序入口"""

import sys
import logging
import argparse
from pathlib import Path

from .config import Config
from .exchange import BinanceExchange
from .risk_manager import RiskManager
from .strategy import MartingaleStrategy


def setup_logging(log_level: str = "INFO"):
    """
    设置日志配置
    
    Args:
        log_level: 日志级别
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='币安马丁格尔交易框架')
    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='配置文件路径 (默认: config.yaml)'
    )
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='日志级别 (默认: INFO)'
    )
    parser.add_argument(
        '--testnet',
        action='store_true',
        help='使用币安测试网'
    )
    
    args = parser.parse_args()
    
    # 设置日志
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    try:
        # 如果指定了--testnet，设置环境变量
        if args.testnet:
            import os
            os.environ['BINANCE_TESTNET'] = 'true'
            logger.info("已启用测试网模式")
        
        # 加载配置
        logger.info(f"加载配置文件: {args.config}")
        config = Config(args.config)
        
        # 确定是否使用测试网（命令行参数优先）
        use_testnet = args.testnet or config.testnet
        
        # 创建交易所连接
        logger.info(f"初始化交易所连接... (测试网: {use_testnet})")
        
        # 检查API密钥
        api_key = config.api_key
        api_secret = config.api_secret
        
        if use_testnet:
            if not api_key or not api_secret:
                logger.warning("测试网模式下未设置API密钥，某些功能可能无法使用")
                logger.info("提示：币安测试网API密钥可在 https://testnet.binancefuture.com/ 申请")
            elif api_key and api_secret:
                logger.info("使用测试网API密钥")
        else:
            if not api_key or not api_secret:
                raise ValueError("实盘模式必须设置 BINANCE_API_KEY 和 BINANCE_SECRET_KEY")
        
        exchange = BinanceExchange(
            api_key=api_key,
            api_secret=api_secret,
            testnet=use_testnet
        )
        
        # 测试连接
        try:
            balance = exchange.get_balance()
            if balance['total'] > 0 or not use_testnet:
                logger.info(f"账户余额: {balance['total']:.2f} USDT (可用: {balance['free']:.2f} USDT)")
            else:
                logger.warning("无法获取账户余额，可能是API密钥无效")
                if use_testnet:
                    logger.info("提示：请确保使用测试网专用的API密钥")
                    logger.info("测试网API密钥申请地址: https://testnet.binancefuture.com/")
        except Exception as e:
            if use_testnet:
                logger.warning(f"测试网连接测试失败: {e}")
                logger.info("提示：测试网需要专用的API密钥，可在 https://testnet.binancefuture.com/ 申请")
            else:
                raise
        
        # 创建风险管理器
        risk_manager = RiskManager(exchange, config)
        
        # 创建策略
        strategy = MartingaleStrategy(exchange, risk_manager, config)
        
        # 运行策略
        strategy.run()
        
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"程序运行错误: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

