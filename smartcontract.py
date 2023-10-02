from pyteal import *
import datetime
from datetime import datetime, timezone

#default values
host_addr = Addr ("GCYOXCBLUWFJMRH4B6TGL2HO5RB6SW3ZTOREXCIIY7ERVJGYZ463QPG7QU")
guest_addr = Addr ("6JTXVG2MDQL7W5I77RCA62C5OTBZLYTPVHXC43RFNGEKTCAHMQAMHNJ2AE")
service_addr = Addr ("F66DD432HVSH5MOU4RCD3WOLNK4VQO4GT4RBZ3KGZE7GBNQZE65HVUSLGA")

fee_limit = Int (10000)

def calculate_timestamp(year, month, day, hour=0, minute=0, second=0):
    # Create a datetime object for the specified date and time
    dt = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    
    # Calculate the timestamp (seconds since the epoch)
    timestamp = dt.timestamp()
    return timestamp

#get check-in date and time from application, to set the first_valid() of the smart contract
#check_in_time = calculate_timestamp()
#check_out_time = calculate_timestamp()

def approval_program():
    handle_creation = Seq([
        #get deposit and rental amount from application
        App.globalPut(Bytes("deposit"),Int(0)),
        App.globalPut(Bytes("rental"),Int(0)),
        App.globalPut(Bytes("total"),Int(0)),
        Return(Int(1))
    ])

    handle_optin = Return(Int(1))
    handle_closeout = Return(Int(1))
    handle_updateapp = Return(Int(1))
    handle_deleteapp = Return(Int(1))

    App.globalPut(Bytes("deposit"),Int(300))
    App.globalPut(Bytes("rental"),Int(1000))
    scratchDeposit = ScratchVar(TealType.uint64)
    scratchRental = ScratchVar(TealType.uint64)
    scratchDeposit.store(App.globalGet(Bytes("deposit")))
    scratchRental.store(App.globalGet(Bytes("rental")))
    App.globalPut(Bytes("total"),scratchDeposit.load()+scratchRental.load())
    
    #for demonstration purpose, but timestamp will be set to now
    check_in_time = Int(int(datetime.timestamp(datetime.now())))
    check_out_time = Int(int(datetime.timestamp(datetime.now())))

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
			TxnField.amount:App.globalGet(Bytes("total"))
		}),
		InnerTxnBuilder.Submit(),
        Return(Int(1))
    ])
        
    deposit_not_refunded= Seq(
        Assert(is_host_request),
		InnerTxnBuilder.Begin(),
		InnerTxnBuilder.SetFields({
			TxnField.type_enum: TxnType.Payment,
			TxnField.sender:host_addr,
			TxnField.receiver:service_addr,
			TxnField.amount:App.globalGet(Bytes("deposit"))
		}),
		InnerTxnBuilder.Submit(),
        Return(Int(1))
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

# Write to file
appFile = open('approval.teal', 'w')
appFile.write(approval_program())
appFile.close()

clearFile = open('clear.teal', 'w')
clearFile.write(clear_state_program())
clearFile.close()





	
	
		
		

		
		
		
		
		


	