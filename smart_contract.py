from pyteal import *
import datetime
from datetime import datetime, timezone

class LocalState:
    """ wrapper class for access to predetermined Local State properties"""
    class Schema:
        """ Local State Schema """
        NUM_UINTS: TealType.uint64  = Int(2)
        NUM_BYTESLICES: TealType.uint64  = Int(0)

    class Variables:
        """ Local State Variables """
        PAID_AMOUNT: TealType.bytes = Bytes("paid_amount")
        LAST_PAYMENT_TIMESTAMP: TealType.bytes = Bytes("last_payment_timestamp")


class GlobalState:
    """ wrapper class for access to predetermined Global State properties"""
    class Schema:
        """ Global State Schema """
        NUM_UINTS: TealType.uint64 = Int(6)
        NUM_BYTESLICES: TealType.uint64 = Int(0)
        

    class Variables:
        """ Global State Variables """
        RENTAL: TealType.bytes = Bytes("rental")
        DEPOSIT: TealType.bytes = Bytes("deposit")
        TOTAL: TealType.bytes = Bytes("total")
        CANCELLED: TealType.bytes = Bytes("cancelled")
        PAID: TealType.bytes = Bytes("paid")
        ASSET_ID: TealType.bytes = Bytes("assetID")

# --- Global Getters ---
def getAssetId():
    return App.globalGet(GlobalState.Variables.ASSET_ID)

def getRental():
    return App.globalGet(GlobalState.Variables.RENTAL)

def getDeposit():
    return App.globalGet(GlobalState.Variables.DEPOSIT)

def getTotal():
    return App.globalGet(GlobalState.Variables.TOTAL)

def getCancelledStatus():
    return App.globalGet(GlobalState.Variables.CANCELLED)

def getPaymentStatus():
    return App.globalGet(GlobalState.Variables.PAID)

# --- Local Getters ---

def getPaidAmount(account: TealType.bytes):
    return App.localGet(account, LocalState.Variables.PAID_AMOUNT)

def getLastPaidTimestamp(account: TealType.bytes):
    return App.localGet(account, LocalState.Variables.LAST_PAYMENT_TIMESTAMP)


#default values
host_addr = Addr ("GCYOXCBLUWFJMRH4B6TGL2HO5RB6SW3ZTOREXCIIY7ERVJGYZ463QPG7QU")
guest_addr = Addr ("6JTXVG2MDQL7W5I77RCA62C5OTBZLYTPVHXC43RFNGEKTCAHMQAMHNJ2AE")
service_addr = Addr ("F66DD432HVSH5MOU4RCD3WOLNK4VQO4GT4RBZ3KGZE7GBNQZE65HVUSLGA")

#Tools
def calculate_timestamp(year, month, day, hour=0, minute=0, second=0):
    # Create a datetime object for the specified date and time
    dt = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    
    # Calculate the timestamp (seconds since the epoch)
    timestamp = dt.timestamp()
    return timestamp

def inner_asset_creation() -> Expr:
    """
    - returns the id of the generated asset or fails
    """
    call_parameters = Gtxn[1].application_args
    return Seq([
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            #TxnField.note: Bytes("TUT_ITXN_AC"),
            TxnField.type_enum: TxnType.AssetConfig,
            TxnField.config_asset_clawback: Global.current_application_address(),
            TxnField.config_asset_reserve: Global.current_application_address(),
            TxnField.config_asset_default_frozen: Int(1),
            TxnField.config_asset_metadata_hash: call_parameters[0],
            TxnField.config_asset_name: call_parameters[1],
            TxnField.config_asset_unit_name: call_parameters[2],
            TxnField.config_asset_total: Int(1),
            TxnField.config_asset_decimals: Int(0),
            TxnField.config_asset_url: call_parameters[3],
        }),
        InnerTxnBuilder.Submit(),
        App.globalPut(GlobalState.Variables.ASSET_ID, InnerTxn.created_asset_id())
    ])

def inner_asset_transfer(asset_id: TealType.uint64, asset_amount: TealType.uint64, asset_sender: TealType.bytes, asset_receiver: TealType.bytes) -> Expr:
    return Seq([
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            #TxnField.note: Bytes("TUT_ITXN_AT"),
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: asset_id,
            TxnField.asset_sender: asset_sender,
            TxnField.asset_amount: asset_amount,
            TxnField.asset_receiver: asset_receiver
            }),
        InnerTxnBuilder.Submit()
    ])

def inner_payment_txn(amount: TealType.uint64, receiver: TealType.bytes) -> Expr:
    return Seq([
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            #TxnField.note: Bytes("TUT_ITXN_PAY"),
            TxnField.type_enum: TxnType.Payment,
            TxnField.sender: Global.current_application_address(),
            TxnField.amount: amount,
            TxnField.receiver: receiver
            }),
        InnerTxnBuilder.Submit()
    ])

#get check-in date and time from application, to set the first_valid() of the smart contract
#check_in_time = calculate_timestamp()
#check_out_time = calculate_timestamp()

#for demonstration purpose, timestamp will be set to now
check_in_time = Int(int(datetime.timestamp(datetime.now())))
check_out_time = Int(int(datetime.timestamp(datetime.now())))

class TxnTags:
    """ TxnTags for operations identification """
    SETUP: TealType.bytes = Bytes("SETUP")
    ALGO_PAYMENT: TealType.bytes = Bytes("ALGO_PAYMENT")
    ASSET_HANDIN: TealType.bytes = Bytes("ASSET_HANDIN")
    COLLECT_RENTAL: TealType.bytes = Bytes("COLLECT_RENTAL")
    CHECKOUT: TealType.bytes = Bytes("CHECKOUT")

def is_acc_opted_in(account: TealType.bytes):
    return App.optedIn(account, Global.current_application_id())

def is_valid_creation_call():
    return Seq(
	Assert(Txn.sender() == host_addr),
        Assert(Txn.type_enum() == TxnType.ApplicationCall),
        Assert(Txn.on_completion() == OnComplete.NoOp),
        Assert(Txn.global_num_byte_slices() == Int(0)),
        Assert(Txn.global_num_uints() == Int(3)),
        Assert(Txn.local_num_byte_slices() == Int(0)),
        Assert(Txn.local_num_uints() == Int(0)),
        Int(1))

def is_valid_setup_call(fund_txn_index: TealType.uint64, app_call_txn_index: TealType.uint64):
    return Seq(
        # first transaction is seeding the application account
        Assert( Gtxn[fund_txn_index].sender() == host_addr),
        Assert( Gtxn[fund_txn_index].type_enum() == TxnType.Payment ),
	    Assert( Gtxn[app_call_txn_index].sender() == host_addr),
        Assert( Gtxn[app_call_txn_index].type_enum() == TxnType.ApplicationCall ),
        Assert( Gtxn[app_call_txn_index].on_completion() == OnComplete.NoOp ),
        Assert( Gtxn[app_call_txn_index].application_id() != Int(0) ),
        # the correct amount of application_args are specified
        Assert( Gtxn[app_call_txn_index].application_args.length() == Int(6) ),
        Int(1))

def setup_app( ):
    """ perform application setup to initiate global state and create the managed ASA"""
    rental = Gtxn[1].application_args[4]
    deposit = Gtxn[1].application_args[5]
    return Seq(
        inner_asset_creation(),
        # initiate Global State
        App.globalPut(GlobalState.Variables.DEPOSIT, Btoi(deposit)),
        App.globalPut(GlobalState.Variables.RENTAL, Btoi(rental)),
        App.globalPut(GlobalState.Variables.TOTAL, Btoi(getDeposit())+ Btoi(getRental())),
        Int(1))


def is_valid_booking_call(
    app_call_txn_index: TealType.uint64,
    payment_txn_index: TealType.uint64,
    asset_id: TealType.uint64
    ):
    # the first transaction sends the microAlgos to pay for the ASA units
    payment_txn = Gtxn[payment_txn_index]
    # the application call just triggers the correct application logic
    app_call_txn = Gtxn[app_call_txn_index]
    return Seq(
	Assert( app_call_txn.sender() == guest_addr ),
        Assert( is_acc_opted_in(app_call_txn.sender()) ),
        Assert( app_call_txn.type_enum() == TxnType.ApplicationCall ),
        Assert( app_call_txn.on_completion() == OnComplete.NoOp ),
        Assert( payment_txn.type_enum() == TxnType.Payment ),
        Assert( app_call_txn.sender() ==  payment_txn.sender() ),
        # correct asset gets sent
        Assert( app_call_txn.assets[0] == asset_id ),
        # enough money sent to buy at least 1 unit
        Assert( payment_txn.amount() >= getTotal() ),
        Int(1))


def booking (payment_txn_index: TealType.uint64, asset_id: TealType.uint64):
    """ perform the operation to book """
    payment_txn = Gtxn[payment_txn_index]
    amount_sent = payment_txn.amount()
    
    refund_amount = amount_sent - getTotal()

    return Seq(
        If(amount_sent >= getTotal()).Then(
            inner_asset_transfer(
                asset_id,
                Int(1),
                Global.current_application_address(),
                payment_txn.sender())
            ),
        #refund if the sender paid too much
        If(refund_amount > Int(0)).Then(
            inner_payment_txn(refund_amount, payment_txn.sender())
        ),
	# update local state
        App.localPut(payment_txn.sender(), LocalState.Variables.PAID_AMOUNT, getTotal()),
        App.localPut(
            payment_txn.sender(),
            LocalState.Variables.LAST_PAYMENT_TIMESTAMP,
            Global.latest_timestamp()),
	# update global state
	    App.globalPut(GlobalState.Variables.PAID, Int(1)),
        Int(1))

def is_eligible_for_refund():
    """ check if eligible for refund """
    return ( Global.latest_timestamp() <= check_in_time )

def cancellation_refund_request():
    refund_amount = getTotal()
    current_paid_amount = getPaidAmount(Txn.sender())
    updated_paid = Minus(current_paid_amount, refund_amount)

    return Seq(
        # if is refund period still active then refund
        If(is_eligible_for_refund()).Then(
            Seq(
                inner_asset_transfer(
                getAssetId(),
                Int(1),
                Txn.sender(),
                Global.current_application_address()),

                inner_payment_txn(refund_amount, Txn.sender()),
                App.localPut(
                    Txn.sender(),
                    LocalState.Variables.PAID_AMOUNT, updated_paid),
		        App.globalPut(GlobalState.Variables.CANCELLED, Int(1)),
                Int(1))
        # Else the call gets rejected
        ).Else(Int(0)))

def is_valid_refund_call():
    asset_id = getAssetId()
    current_paid_amount = getPaidAmount(Txn.sender())
    refund = getTotal()
    return Seq(
	Assert( Txn.sender() == guest_addr ),
        Assert( is_acc_opted_in(Txn.sender()) ),
        Assert( Txn.on_completion() == OnComplete.NoOp ),
        Assert( refund == getTotal() ),
        # only refund if the payment is made previously
        Assert( current_paid_amount >= refund ),
        Assert( Txn.assets[0] == asset_id ),
        Int(1))

def collect_rental():
    """ collect rental """
    rental = getRental()
    cancelled = getCancelledStatus()
    paid = getPaymentStatus()
    return Seq(
        If(And(
            Not(is_eligible_for_refund()), 
            paid == Int(1), 
            cancelled == Int(0),
            Txn.sender() == host_addr,)
        ).Then(
            inner_payment_txn(rental, Txn.sender()),
        ),
        Int(1)
    )
    

def check_out(refund_deposit: TealType.uint64):
    """ contract revoke asset """
    asset_id = getAssetId()
    deposit = getDeposit()
    return Seq(
        Assert(Txn.sender()==host_addr),
        Assert(Global.latest_timestamp() >= check_out_time),
	    inner_asset_transfer(
            asset_id,
            Int(1),
            guest_addr,
            Global.current_application_address()),
        If(refund_deposit == Int(0)).Then(
            inner_payment_txn(deposit, service_addr)
        ).Else(
            inner_payment_txn(deposit, guest_addr)
        ),
        Int(1)
    )

# --- Approval Program ---

def approval_program():
    """approval program for the contract"""

# App Lifecycle
    handle_creation = is_valid_creation_call()
    handle_closeout = Int(0)
    handle_deleteapp =  Int(0)
    handle_clear_state = Int(0)
    handle_optin = Int(1) 
    collect_rental_status = collect_rental()
    check_out_status = check_out(Btoi(Txn.application_args[0]))

# Setup Operation
    setup_app_operation = And(
        is_valid_setup_call(Int(0), Int(1)),
        setup_app())

# Booking operation
    booking_operation = And(
        is_valid_booking_call(
            Int(1),
            Int(0),
            getAssetId()),
        booking(int(0), getAssetId()))

# Refund operation
    refund_operation = And(
        is_valid_refund_call(),
        cancellation_refund_request())

# Main Conditional
    program = Cond(
        [ Global.group_size () == Int(1),
            Cond(
                [ Txn.application_id() == Int(0), Return(handle_creation) ],
                [ BytesEq(Txn.note(), TxnTags.ASSET_HANDIN), Return(refund_operation)],
                [ BytesEq(Txn.note(), TxnTags.COLLECT_RENTAL), Return(collect_rental_status)],
                [ BytesEq(Txn.note(), TxnTags.CHECKOUT), Return(check_out_status)],
                [ Txn.on_completion() == OnComplete.DeleteApplication, Return(handle_deleteapp) ],
                [ Txn.on_completion() == OnComplete.ClearState, Return(handle_clear_state) ],
                [ Txn.on_completion() == OnComplete.OptIn, Return(handle_optin) ],
                [ Txn.on_completion() == OnComplete.CloseOut, Return(handle_closeout) ]
                )],
        [ Global.group_size() == Int(2),
            Cond(
                [ BytesEq(Gtxn[1].note(), TxnTags.SETUP), Return(setup_app_operation) ],
                [ BytesEq(Gtxn[1].note(), TxnTags.ALGO_PAYMENT), Return(booking_operation) ]
                )],
        [ Global.group_size() >= Int(2), Reject() ]
        )
    return compileTeal(program, Mode.Application, version=5)

def clear_state_program():
    program = Return(Int(0))
    return compileTeal(program, Mode.Application, version=5)

# Write to file
appFile = open('approval.teal', 'w')
appFile.write(approval_program())
appFile.close()

clearFile = open('clear.teal', 'w')
clearFile.write(clear_state_program())
clearFile.close()


