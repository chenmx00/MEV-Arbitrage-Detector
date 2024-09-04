#!/usr/bin/python3
import logging
import json
from moralis import evm_api
logging.basicConfig(level=logging.CRITICAL)
logger = logging.getLogger()
moralis_api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJub25jZSI6IjAyNDU2YzIzLWY0MTEtNDQ1NC05ODQyLWM2MjM5ZDM0NjU4MiIsIm9yZ0lkIjoiNDA0NDYxIiwidXNlcklkIjoiNDE1NTk4IiwidHlwZUlkIjoiY2NkOTgzNWUtM2Q5Ny00NWM0LWE4YWUtZjUyNjY0M2I0NWQ2IiwidHlwZSI6IlBST0pFQ1QiLCJpYXQiOjE3MjM1MDI4ODQsImV4cCI6NDg3OTI2Mjg4NH0.tdBEUcaxi-op9ysnyLHpOm8mo8zyl5phdlBuh1TXTrM"
bnb_address = "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c"

#Helper method
def find_cycle(graph, start):
    def dfs(graph, node):
        if node not in graph:
            return False
        ret = False
        for nbr in graph[node]:
            if nbr == start:
                return True
            ret = ret or dfs(graph, nbr)
        return ret
    return dfs(graph, start)

#Helper method
def check_balance_positive(balance):
    arbitrage = False
    for _, size in balance.items():
        if size < 0:
            return False
        if size > 0:
            arbitrage = True
    return arbitrage

#Helper method
def twos_complement(n, w):
    if n & (1 << (w - 1)): n = n - (1 << w)
    return n    

#Helper method
def address_convert(address):
    return "0x"+address[26:]

#Helper method
def update_balances(balances, address_from, address_to, token, value):
    if address_from not in balances:
        balances[address_from] = {}
    if token not in balances[address_from]:
        balances[address_from][token] = 0
    balances[address_from][token] -= value
    if address_to not in balances:
        balances[address_to] = {}
    if token not in balances[address_to]:
        balances[address_to][token] = 0
    balances[address_to][token] += value
    return balances

#Helper method
def query_token_price_batch(token_price_query_per_tx, block):
    body = {"tokens" : []}
    for token_address in token_price_query_per_tx:
        body["tokens"].append({"token_address" : token_address, "to_block": str(block)})
    params = {
        "chain": "bsc",
    }
    try:
        results = evm_api.token.get_multiple_token_prices(
            api_key=moralis_api_key,
            body=body,
            params=params,
        )
    except Exception as e:
        logger.error({f"Connection Error."})
        raise e
    token_price_map = {}
    for result in results:
        token_price_map[result["tokenAddress"]] = result
    return token_price_map

def process_pnl(arb_res_block, block):
    arb_revenue_per_block = {}

    #fetch all the prices for arbitraged token in the current block with the correspondent block time price.
    token_price_query_per_block = set()
    for arb_tx in arb_res_block:
        for token in arb_tx[2]:
            token_price_query_per_block.add(token[0])
    token_price_query_per_block.add(bnb_address)# get the wbnb price for this block to compute the cost later.
    token_price_map = query_token_price_batch(token_price_query_per_block, block)

    for arb_tx in arb_res_block:
        tid = arb_tx[0]
        tx_hash = arb_tx[1]
        gas_used = arb_tx[3]
        gas_price = arb_tx[4]
        arb_revenue_per_tx = {}
        for token in arb_tx[2]:
            arb_token_address = token[0]
            arb_token_size = token[1]
            arb_token_price_info = token_price_map[arb_token_address]
            arb_token_symbol = arb_token_price_info["tokenSymbol"]
            arb_token_decimal = arb_token_price_info["tokenDecimals"]
            arb_token_price_usd = float(arb_token_price_info["usdPriceFormatted"])
            arb_token_amount = arb_token_size / (10 ** int(arb_token_decimal))
            arb_token_revenue = arb_token_price_usd * arb_token_amount
            arb_revenue_per_tx[arb_token_symbol] = arb_token_revenue
        #compute cost per tx
        bnb_price_info = token_price_map[bnb_address]
        bnb_price_usd = float(bnb_price_info["usdPriceFormatted"])
        bnb_decimal = bnb_price_info["tokenDecimals"]
        gas_used_amount = int(gas_used, 16) / (10**int(bnb_decimal))
        total_cost = gas_used_amount * int(gas_price, 16) * bnb_price_usd
        arb_revenue_per_tx["total_cost"] = total_cost
        arb_revenue_per_block[(tid, tx_hash)] = arb_revenue_per_tx    
    return arb_revenue_per_block

def dispatch_block(start_block, end_block):
        for block in range(start_block, end_block+1):
            with open(f"tx_receipts/{block}.json", "r") as block_input:
                logger.debug(f"Processing block {block}")
                receipts = json.load(block_input)
                tid = 0
                arb_res_block = []
                for receipt in receipts[str(block)]:
                    tx_hash = receipt["transactionHash"]
                    arb = process_tx(tx_hash, tid, receipt)
                    if arb:
                        arb_res_block.append(arb)
                    tid += 1
                    #write output files for transaction if to verify correctness
                    with open(f"tests/{block}_res", 'w') as output_path:
                        for arb in arb_res_block:
                            output_path.write(str(arb[0]) + '\n')
            arb_revenue_per_block = process_pnl(arb_res_block, block)
            logger.critical(f"Arbs found in block: {block}")
            for tx,  symbols in arb_revenue_per_block.items():
                tid = tx[0]
                tx_hash = tx[1]
                total_cost = symbols["total_cost"]
                line = ""
                total_revenue = 0.0
                for symbol, revenue in symbols.items():
                    if symbol != "total_cost":
                        revenue = revenue
                        line += symbol
                        line += ": $"
                        line += str(revenue)
                        total_revenue += float(revenue)
                line += f" with total cost ${total_cost}"
                line += f" Profit: ${total_revenue - float(total_cost)}"
                #line += f" {tx_hash}"
                logger.critical(f"Tx {tid}: " + line)

def process_tx(tx_hash, tid, receipt):
    data = receipt["logs"]
    tx_from = receipt["from"]
    tx_to = receipt["to"]
    tx_value = receipt["value"]
    log_id = 0
    balances = {}
    graph = {}
    swapped_address = set()
    sawp_address = set()
    transfer_initiator = None
    logger.debug(f"--Tx: {tid},  Hash: {tx_hash}")

    #If the Tx sender send BNB directly to the Tx_to address, we need to mark it as a transfer
    tx_value_dec = int(tx_value, 16)
    if tx_value_dec:
        if tx_from not in graph:
            graph[tx_from] = []
        graph[tx_from].append(tx_to)
        balances = update_balances(balances, tx_from, tx_to, bnb_address, tx_value_dec)
            
    for log in data:
        log_id += 1

        #Bypass the case where topics0 is an empty list
        if not log["topics"]:
            continue

        #Transfer
        if log["topics"][0] == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef":
            if log["data"] == "0x":
                continue

            address_from = address_convert(log["topics"][1])
            address_to = address_convert(log["topics"][2])
            value = int(log["data"], 16)
            token = log["address"]
            balances = update_balances(balances, address_from, address_to, token, value)
            if address_from not in graph:
                graph[address_from] = []
            graph[address_from].append(address_to)
            if not transfer_initiator:
                transfer_initiator = address_from
            logger.debug(f"----Log: {log_id}, Event: Transfer, From: {address_from}, To: {address_to}, Value: {str(value)}")

        #Deposit
        elif log["topics"][0] == "0xe1fffcc4923d04b559f4d29a8bfc6cda04eb5b0d3c460751c2402c5c5cc9109c":
            #reward case
            if len(log["topics"]) == 1:
                continue
            address_from = tx_from
            address_to = address_convert(log["topics"][1])
            value = int(log["data"], 16)
            token = log["address"]
            balances = update_balances(balances, address_from, address_to, token, value)
            if address_from not in graph:
                graph[address_from] = []
            graph[address_from].append(address_to)
            logger.debug(f"----Log: {log_id}, Event: Deposit, From: {address_from}, To: {address_to}, Value: {str(value)}")

        #Withdraw
        elif log["topics"][0] == "0x7fcf532c15f0a6db0bd6d0e038bea71d30d808c7d98cb3bf7268a95bf5081b65":
            address_from = address_convert(log["topics"][1])
            address_to = tx_from
            value = int(log["data"], 16)
            token = log["address"]
            balances = update_balances(balances, address_from, address_to, token, value)
            if address_from not in graph:
                graph[address_from] = []
            graph[address_from].append(address_to)
            logger.debug(f"----Log: {log_id}, Event: Withdrawl, From: {address_from}, To: {address_to}, Value: {str(value)}")

        #Uniswap_V2
        elif log["topics"][0] == "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822":
            address_from = address_convert(log["topics"][1])
            address_to = address_convert(log["topics"][2])
            value = log["data"][2:]
            amount0In = int(value[:64], 16)
            amount1In = int(value[64:128], 16)
            amount0Out = int(value[128:192], 16)
            amount1Out = int(value[192:256], 16)
            swapped_address.add(address_from)
            swapped_address.add(address_to)
            sawp_address.add(log["address"])
            logger.debug(f"----Log: {log_id}, Event: Uniswap_V2, From: {address_from}, To: {address_to}, Amount0In: {str(amount0In)}, Amount1In: {str(amount1In)}, Amount0Out: {str(amount0Out)}, Amount1Out: {str(amount1Out)}")

        #Uniswap_V3    
        elif log["topics"][0] == "0x19b47279256b2a23a1665c810c8d55a1758940ee09377d4f8d26497a3577dc83":
            address_from = address_convert(log["topics"][1])
            address_to = address_convert(log["topics"][2])
            value = log["data"][2:]
            segLen = int(len(value)/7)
            amount0 = twos_complement(int(value[:segLen], 16),256)
            amount1 = twos_complement(int(value[segLen:2 * segLen], 16),256)
            sqrtPriceX96 = int(value[2*segLen:3*segLen], 16)
            liquidity = int(value[3*segLen:4*segLen], 16)
            tick = twos_complement(int(value[4*segLen:5*segLen], 16),256)
            protocolFeesToken0 = int(value[5*segLen:6*segLen], 16)
            protocolFeesToken1 = int(value[6*segLen:7*segLen], 16)
            swapped_address.add(address_from)
            swapped_address.add(address_to)
            sawp_address.add(log["address"])
            logger.debug(f"----Log: {log_id}, Event: Uniswap_V3, From: {address_from}, To: {address_to}, Amount0: {str(amount0)}, Amount1: {str(amount1)}, SqrtPriceX96: {str(sqrtPriceX96)}, Liquidity: {str(liquidity)}, Tick: {str(tick)}, ProtocolFeesToken0: {str(protocolFeesToken0)}, ProtocolFeesToken1: {str(protocolFeesToken1)}")
        
        #Pancakeswap_V2
        elif log["topics"][0] == "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822":
            address_from = address_convert(log["topics"][1])
            address_to = address_convert(log["topics"][2])
            value = log["data"][2:]
            amount0In = int(value[:64], 16)
            amount1In = int(value[64:128], 16)
            amount0Out = int(value[128:192], 16)
            amount1Out = int(value[192:256], 16)
            swapped_address.add(address_from)
            swapped_address.add(address_to)
            sawp_address.add(log["address"])
            logger.debug(f"----Log: {log_id}, Event: Pancakeswap_V2, From: {address_from}, To: {address_to}, Amount0In: {str(amount0In)}, Amount1In: {str(amount1In)}, Amount0Out: {str(amount0Out)}, Amount1Out: {str(amount1Out)}")
        
        #Pancakeswap_V3
        elif log["topics"][0] == "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67":
            address_from = address_convert(log["topics"][1])
            address_to = address_convert(log["topics"][2])
            value = log["data"][2:]
            segLen = int(len(value)/5)
            amount0 = twos_complement(int(value[:segLen], 16),256)
            amount1 = twos_complement(int(value[segLen:2 * segLen], 16),256)
            sqrtPriceX96 = int(value[2*segLen:3*segLen], 16)
            liquidity = int(value[3*segLen:4*segLen], 16)
            tick = twos_complement(int(value[4*segLen:5*segLen], 16),256)
            swapped_address.add(address_from)
            swapped_address.add(address_to)
            sawp_address.add(log["address"])
            logger.debug(f"----Log: {log_id}, Event: Pancakeswap_V3, From: {address_from}, To: {address_to}, Amount0: {str(amount0)}, Amount1: {str(amount1)}, SqrtPriceX96: {str(sqrtPriceX96)}, Liquidity: {str(liquidity)}, Tick: {str(tick)}")

        #Sync
        elif log["topics"][0] == "0x1c411e9a96e071241c2f21f7726b17ae89e3cab4c78be50e062b03a9fffbbad1" or log["topics"][0] == "0xcf2aa50876cdfbb541206f89af0ee78d44a2abf8d328e37fa4917f982149848a":
            logger.debug(f"----Log: {log_id}, Event: Sync")

        #Approval
        elif log["topics"][0] == "0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925":
            logger.debug(f"----Log: {log_id}, Event: Approval")

        #Log_named_uint
        elif log["topics"][0] == "0xb2de2fbe801a0df6c0cbddfd448ba3c41d48a040ca35c56c8196ef0fcae721a8":
            logger.debug(f"----Log: {log_id}, Event: Log_names_uint")

        #Fees
        elif log["topics"][0] == "0x112c256902bf554b6ed882d2936687aaeb4225e8cd5b51303c90ca6cf43a8602":
            logger.debug(f"----log: {log_id}, Event: Fee")

        #Disptach
        elif log["topics"][0] == "0x7389f47b3c4b3844581f85248e71f29d7ae82d09bd7c35c08580f9a81c12b977":
            logger.debug(f"----log: {log_id}, Event: Dispatch")
        
        #SwapBuyFee
        elif log["topics"][0] == "0x4abc90906bcf0a69afb9366cc077ec9e392a2176e798a1330653f1af8f158fab":
            logger.debug(f"----log: {log_id}, Event: SwapBuyFee")
        
        #TransferFee
        elif log["topics"][0] == "0xaceae1c38c10ab5f1b31e281476f40242c0b5f1dd3623de09b7a383036f79298":
            logger.debug(f"----log: {log_id}, Event: TransferFee")
        
        #LandStaked
        elif log["topics"][0] == "0xe4474d71e62a902a1090aa1357af162a16ca11976430f4a52459ab0abba50910":
            logger.debug(f"----log: {log_id}, Event: LandStaked")
        
        #PriceUpdate
        elif log["topics"][0] == "0xc37a77b91cc3fc2d0e4b43fd2f347ec67adda10e39215de4742836cc3e42c97a":
            logger.debug(f"----log: {log_id}, Event: PriceUpdate")

        #UserSignedIn
        elif log["topics"][0] == "0xf5376aeffebf2186e2683b226ecebef47155a0b205a74efc2469f47e071a8490":
            logger.debug(f"----log: {log_id}, Event: UserSignedIn")

        #Unknown
        else:
            logger.debug(f"----Log: {log_id}, Event: Unknown")
    arb = False
    for address, balance in balances.items():
        if check_balance_positive(balance):
            #handle the case the arbitrageur transfer money from the arbitrage address to an external address in the last transfer in the tx
            if tx_to in graph and address in graph[tx_to] and address not in graph:
                address = tx_to
            #the effective abitraged address can't be a swap contract address
            if address in sawp_address:
                continue
            #abitrage must involves more than two swaps
            if len(sawp_address) < 2:
                continue
            #Effective arbitraged address is either an EOA who starts the transfer chains in a tx or the to_address(the one intereacted with contracts) of the tx
            if address != tx_to and address != tx_from and address != transfer_initiator:
                continue
            #effective arbitraged address must be in the swapped chain
            if address not in swapped_address:
                continue
            #token is burnt in this case
            if int(address, 16) == 0:
                continue
            #an effective arbitraged address must be in at least a swapping cycle
            if not find_cycle(graph, address):
                continue
            #avoid case where tx_from directly send money to tx_to
            if tx_from in graph and tx_to in graph[tx_from]:
                continue
            logger.debug(address)
            arb = True
            arb_tokens = []
            for token, size in balance.items():
                if size > 0:
                    arb_tokens.append([token, size])
                    logger.debug(f"arbitrage found: token {str(token)} size {str(size)} on {tx_hash}")
    if arb:
        gas_used = receipt["gasUsed"]
        gas_price = receipt["gas_price"]
        return [tid, tx_hash, arb_tokens, gas_used, gas_price]
    else:
        return []
            
def main():
    dispatch_block(40784970, 40784980)

if __name__ == "__main__":
    main()


    