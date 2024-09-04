#!/usr/bin/python3
import httpx
import logging
import time
import json
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
blocks = {}
def get_txs_by_block(start_block, end_block):
    url = "https://docs-demo.bsc.quiknode.pro/"
    headers = {
        "Content-Type": "application/json"
    }
    with httpx.Client() as client:
        for block in range(start_block, end_block+1):
            params = {
            "jsonrpc": "2.0",
            "method": "eth_getBlockByNumber",
            "params": [hex(block),False],
            "id": 1,
        }
            try:
                time.sleep(0.2)
                response = client.post(url, json=params, headers=headers)
                blockinfo = response.json()["result"]
                blocks[str(block)] = blockinfo["transactions"]
                logger.info(f"Block {block}: All tx hashs fetched")
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error occurred: {e}")
            except httpx.RequestError as e:
                logger.error(f"Request error occurred: {e}")
            except Exception as e:
                logger.error(f"An unexpected error occurred: {e}")

def get_tx_receipt_by_tx_hash():
    url = "https://docs-demo.bsc.quiknode.pro/"
    headers = {
        "Content-Type": "application/json"
    }
    with httpx.Client() as client:
        for block in blocks.keys():
            with open(f"tx_receipts/{block}.json", 'w') as output_path:
                tid = 0
                to_write = {}
                to_write[str(block)] = []
                for tx_hash in blocks[block]:
                    params_receipt = {
                        "jsonrpc": "2.0",
                        "method": "eth_getTransactionReceipt",
                        "params": [tx_hash],
                        "id": 1,
                    }
                    params_tx_by_hash = {
                        "jsonrpc": "2.0",
                        "method": "eth_getTransactionByHash",
                        "params": [tx_hash],
                        "id": 1,
                    }
                    try:
                        time.sleep(0.2)
                        response_recipt = client.post(url, json=params_receipt, headers=headers)
                        response_recipt.raise_for_status()
                        time.sleep(0.2)
                        response_tx_by_hash = client.post(url, json=params_tx_by_hash, headers=headers)
                        response_tx_by_hash.raise_for_status()
                        tx_by_hash_result = response_tx_by_hash.json()["result"]
                        tx_value = tx_by_hash_result["value"]
                        gas_price = tx_by_hash_result["gasPrice"]
                        gas = tx_by_hash_result["gas"]
                        tx_receipt_result = response_recipt.json()["result"]
                        tx_receipt_result["value"] = tx_value
                        tx_receipt_result["gas_price"] = gas_price
                        tx_receipt_result["gas"] = gas
                        to_write[str(block)].append(tx_receipt_result)
                        #json.dump(response.json(), output_path)
                        logger.info(f"Block {block}: Tx {tid} is written")
                        tid += 1
                    except httpx.HTTPStatusError as e:
                        logger.error(f"HTTP error occurred: {e}")
                    except httpx.RequestError as e:
                        logger.error(f"Request error occurred: {e}")
                    except Exception as e:
                        logger.error(f"An unexpected error occurred: {e}")
                json.dump(to_write, output_path)
                logger.info(f"Tx receipts for Block {block} has been written to tx_receipts/{block}.json")


def main():
    get_txs_by_block(40784970, 40784980)
    get_tx_receipt_by_tx_hash()

if __name__ == "__main__":
    main()




