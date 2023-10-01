from pyteal import *
import decimal, datetime
from datetime import datetime, timezone

#default values
host_addr = Addr ("HOST_ADDR")
guest_addr = Addr ("GUEST_ADDR")
service_addr = Addr ("SERVICE_ADDR")

#get deposit and rental amount from application
deposit = decimal(amount)
rental = decimal(amount)

fee_limit = Int (10000)

def calculate_timestamp(year, month, day, hour=0, minute=0, second=0):
    # Create a datetime object for the specified date and time
    dt = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    
    # Calculate the timestamp (seconds since the epoch)
    timestamp = dt.timestamp()
    
    return timestamp

#get check-in date and time from application
check_in_time = calculate_timestamp(CHECK_IN)
check_out_time = calculate_timestamp(CHECK_OUT)

def full_payment():
    handle_creation = Return(Int(1))
    handle_optin = Return(Int(1))
    handle_closeout = Return(Int(1))
    handle_updateapp = Return(Int(1))
    handle_deleteapp = Return(Int(1))

    fullpay_cond = And(
		Txn.fee() < fee_limit,
		Txn.first_valid() > check_in_time
	    )

	# Check if the transaction is a call from the host to take the deposit
    is_host_request = And(
		Txn.fee() < fee_limit,
		Txn.first_valid() > check_out_time,
        Txn.sender() == host_addr
        )
		
    full_payment = Seq([
        Assert(fullpay_cond), 
		InnerTxnBuilder.Begin(),
		InnerTxnBuilder.SetFields({
			TxnField.type_enum: TxnType.Payment,
			TxnField.sender:guest_addr,
			TxnField.receiver:host_addr,
			TxnField.amount:rental+deposit
		}),
		InnerTxnBuilder.Submit(),
    ]  
    )
        
    deposit_not_refunded= Seq(
        Assert(is_host_request),
		InnerTxnBuilder.Begin(),
		InnerTxnBuilder.SetFields({
			TxnField.type_enum: TxnType.Payment,
			TxnField.sender:host_addr,
			TxnField.receiver:service_addr,
			TxnField.amount:deposit
		    }),
		InnerTxnBuilder.Submit()	
	)
		
		
    handle_noop = Seq(
        Assert(Global.group_size() == Int(1)), 
        Cond(
        		[Txn.application_args[0] == Bytes("FullPayment"), full_payment], 
        		[Txn.application_args[0] == Bytes("DepositNotRefunded"), deposit_not_refunded]
        	)
    	)

    program = Cond(
		    [Txn.application_id() == Int(0), handle_creation],
        	[Txn.on_completion() == OnComplete.OptIn, handle_optin],
        	[Txn.on_completion() == OnComplete.CloseOut, handle_closeout],
        	[Txn.on_completion() == OnComplete.UpdateApplication, handle_updateapp],
        	[Txn.on_completion() == OnComplete.DeleteApplication, handle_deleteapp],
        	[Txn.on_completion() == OnComplete.NoOp, handle_noop]
    	)
	
    return compileTeal(program, Mode.Application, version=5)


def clear_state_program():
    program = Return(Int(1))
    return compileTeal(program, Mode.Application, version=5)





	
	
		
		

		
		
		
		
		


	