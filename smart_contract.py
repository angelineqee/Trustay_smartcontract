from pyteal import *
import datetime
from datetime import datetime, timezone
from InnerTxnUtils import (inner_payment_txn, inner_asset_creation, inner_asset_transfer)

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
        NUM_UINTS: TealType.uint64 = Int(5)
        NUM_BYTESLICES: TealType.uint64 = Int(1)
        

    class Variables:
        """ Global State Variables """
        RENTAL: TealType.uint64 = Int(0)
        DEPOSIT: TealType.uint64 = Int(0)
        TOTAL: TealType.uint64 = Int(0)
        CANCELLED: TealType.uint64 = Int(0)
        PAID: TealType.uint64 = Int(0)
        ASSET_ID: TealType.bytes = Bytes("asset_ID")


#default values
host_addr = Addr ("GCYOXCBLUWFJMRH4B6TGL2HO5RB6SW3ZTOREXCIIY7ERVJGYZ463QPG7QU")
guest_addr = Addr ("6JTXVG2MDQL7W5I77RCA62C5OTBZLYTPVHXC43RFNGEKTCAHMQAMHNJ2AE")
service_addr = Addr ("F66DD432HVSH5MOU4RCD3WOLNK4VQO4GT4RBZ3KGZE7GBNQZE65HVUSLGA")

def calculate_timestamp(year, month, day, hour=0, minute=0, second=0):
    # Create a datetime object for the specified date and time
    dt = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    
    # Calculate the timestamp (seconds since the epoch)
    timestamp = dt.timestamp()
    return timestamp

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


@Subroutine(TealType.uint64)
def is_acc_opted_in(account: TealType.bytes):
    return App.optedIn(account, Global.current_application_id())

@Subroutine(TealType.uint64)
def is_valid_creation_call():
    return Seq(
	Assert(Txn.sender() == host_addr),
        Assert(Txn.type_enum() == TxnType.ApplicationCall),
        Assert(Txn.on_completion() == OnComplete.NoOp),
        Assert(Txn.global_num_byte_slices() == 0),
        Assert(Txn.global_num_uints() == 3),
        Assert(Txn.local_num_byte_slices() == 0),
        Assert(Txn.local_num_uints() == 0),
        Int(1))

@Subroutine(TealType.uint64)
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

@Subroutine(TealType.uint64)
def setup_app( ):
    """ perform application setup to initiate global state and create the managed ASA"""
    asset_id = inner_asset_creation(Int(1))
    rental = Btoi(Gtxn[1].application_args[1])
    deposit = Btoi(Gtxn[1].application_args[2])
    return Seq(
        # initiate Global State
        App.globalPut(Bytes("deposit"),Int(0)),
	    App.globalPut(GlobalState.Variables.ASSET_ID, asset_id),
        App.globalPut(GlobalState.Variables.DEPOSIT, deposit),
        App.globalPut(GlobalState.Variables.RENTAL, rental),
        App.globalPut(GlobalState.Variables.TOTAL, App.globalGet(Bytes("deposit"))+App.globalGet(Bytes("rental"))),
        Int(1))


@Subroutine(TealType.uint64)
def is_valid_booking_call(
    app_call_txn_index: TealType.uint64,
    payment_txn_index: TealType.uint64,
    asset_id: TealType.uint64,
    total: TealType.uint64
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


@Subroutine(TealType.uint64)
def booking (payment_txn_index: TealType.uint64, asset_id: TealType.uint64):
    """ perform the operation to book """
    payment_txn = Gtxn[payment_txn_index]
    amount_sent = payment_txn.amount()
    
    refund_amount = amount_sent - getTotal()

    return Seq(
        If(amount_sent >= getTotal()).Then(
            inner_asset_transfer(
                asset_id,
                1,
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

@Subroutine(TealType.uint64)
def is_eligible_for_refund():
    """ check if eligible for refund """
    return ( Global.latest_timestamp() <= check_in_time )

@Subroutine(TealType.uint64)
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
                1,
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

@Subroutine(TealType.uint64)
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

@Subroutine(TealType.uint64)
def close_out():
    """ closeout by guest """
    asset_id = getAssetId()
    current_paid_amount = App.localGet(Txn.sender(), LocalState.Variables.PAID_AMOUNT)
    sender_asset_balance = AssetHolding.balance(Txn.sender(), Int(0))

    return Seq(
        # if refund period active send refund
        If(is_eligible_for_refund()).Then(
            inner_payment_txn(current_paid_amount, Txn.sender() ),
        ),
        # check if the sender of the closeout still has units of the ASA
        If(And(sender_asset_balance.hasValue(), sender_asset_balance.value() > Int(0))).
        Then(
            # if so revoke them from the sender closing out of the contract
            inner_asset_transfer(
                asset_id,
                sender_asset_balance.value(),
                Txn.sender(),
                Global.current_application_address())),
        # Clear the Local State of the sender closing out
        App.localDel(Txn.sender(), LocalState.Variables.PAID_AMOUNT),
        App.localDel(Txn.sender(), LocalState.Variables.LAST_PAID_TIMESTAMP),
        Int(1))

@Subroutine(TealType.uint64)
def collect_rental():
    """ collect rental """
    rental = getRental()
    cancelled = getCancelledStatus()
    paid = getPaymentStatus()
    If(And(
        Not(is_eligible_for_refund()), 
        paid == Int(1), 
        cancelled == Int(0)),
        Txn.sender() == host_addr,
        ).Then(
        inner_payment_txn(rental, Txn.sender())
    ).Else(Int(0))

@Subroutine(TealType.uint64)
def check_out():
    """ contract revoke asset """
    asset_id = getAssetId()
    If( And( Global.latest_timestamp() >= check_out_time, Txn.sender() == host_addr ) ).Then(
	inner_asset_transfer(
            asset_id,
            1,
            guest_addr,
            Global.current_application_address())
    )

# Check if the transaction is a call from the host to take the deposit
is_host_request = And(
	Global.latest_timestamp() >= check_out_time,
    Txn.sender() == host_addr
)

@Subroutine(TealType.uint64)
def deposit_not_refunded():
    deposit = getDeposit()
    If (is_host_request).Then(
        inner_payment_txn(deposit, service_addr)
    )


# --- Approval Program ---

def approval_program():
    """approval program for the contract"""

# App Lifecycle
    handle_closeout = close_out()
    handle_app_creation = is_valid_creation_call() 
    handle_deleteapp =  Int(0) 
    handle_clear_state = Int(0) 
    handle_optin = Int(1) 

# Setup Operation
    setup_app_operation = And(
        is_valid_setup_call(Int(0), Int(1)),
        setup_app())

# Booking operation
    booking_operation = And(
        is_valid_booking_call(
            Int(1),
            Int(0),
            getAssetId(),
            getTotal()),
        booking(Int(0), getAssetId()))

# Refund operation
    refund_operation = And(
        is_valid_refund_call(),
        cancellation_refund_request())

# Main Conditional
    program = Cond(
        # Check the group_size() first since if wrong, we dont even have to start
        [ Global.group_size () == Int(1),
            Cond(
                [ Txn.application_id() == Int(0), Return(handle_app_creation) ],
                [ BytesEq(Txn.note(), TxnTags.ASSET_HANDIN), Return(refund_operation)],
                [ Txn.on_completion() == OnComplete.DeleteApplication, Return(handle_deleteapp) ],
                [ Txn.on_completion() == OnComplete.ClearState, Return(handle_clear_state) ],
                [ Txn.on_completion() == OnComplete.OptIn, Return(handle_optin) ],
                [ Txn.on_completion() == OnComplete.CloseOut, Return(handle_closeout) ])],
        [ Global.group_size() == Int(2),
            Cond(
                # like above the note gets checked to determine the intend of the call
                [ BytesEq(Gtxn[1].note(), TxnTags.SETUP), Return(setup_app_operation) ],
                [ BytesEq(Gtxn[1].note(), TxnTags.ALGO_HANDIN), Return(booking_operation) ])],
        [ Global.group_size() >= Int(2), Reject() ]
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


# --- Global Getters ---
@Subroutine(TealType.uint64)
def getAssetId():
    return App.globalGet(GlobalState.Variables.ASSET_ID)

@Subroutine(TealType.uint64)
def getRental():
    return App.globalGet(GlobalState.Variables.RENTAL)

@Subroutine(TealType.uint64)
def getDeposit():
    return App.globalGet(GlobalState.Variables.DEPOSIT)

@Subroutine(TealType.uint64)
def getTotal():
    return App.globalGet(GlobalState.Variables.TOTAL)

@Subroutine(TealType.uint64)
def getCancelledStatus():
    return App.globalGet(GlobalState.Variables.CANCELLED)

@Subroutine(TealType.uint64)
def getPaymentStatus():
    return App.globalGet(GlobalState.Variables.PAID)

# --- Local Getters ---

@Subroutine(TealType.uint64)
def getPaidAmount(account: TealType.bytes):
    return App.localGet(account, LocalState.Variables.PAID_AMOUNT)

@Subroutine(TealType.uint64)
def getLastPaidTimestamp(account: TealType.bytes):
    return App.localGet(account, LocalState.Variables.LAST_PAID_TIMESTAMP)
