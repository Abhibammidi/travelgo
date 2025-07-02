from flask import Flask, render_template, request, redirect, session, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId # Import ObjectId for potential booking IDs
import os
from datetime import datetime

# Flask App Setup
app = Flask(__name__)
app.secret_key = 'e0d15ae2faa18025f4e2a0c7dc5a7b8a830791cc83ad7538667ce14ca2ad8bc0'

# MongoDB Atlas Setup
client = MongoClient('mongodb+srv://abhiram23:abhi23@cluster0.emgafs6.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')
db = client['Travelgo']
users_collection = db['users']
bookings_collection = db['bookings']

# --- Dummy Data (In a real app, these would come from your database) ---
# This is just for demonstration, as we're not persisting bus/train availability yet.
# For actual seat selection, you'd query specific journey's seat data.
dummy_bus_train_data = {
    "Hyderabad_Vijayawada_Orange Travels_08:00 AM": { # Example unique ID for a journey
        "total_seats": 30,
        "booked_seats": ["A1", "A2", "B3"] # Example: These seats are already booked
    },
    "Hyderabad_Vijayawada_Andhra Pradesh Express_06:00": {
        "total_seats": 50,
        "booked_seats": ["C5", "C6", "D1"]
    }
    # Add more entries for other unique bus/train journeys
}
# --- End Dummy Data ---


@app.route('/')
def home():
    return render_template('index.html', logged_in='user' in session)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        if users_collection.find_one({"email": email}):
            return render_template('register.html', message="User already exists.")
        users_collection.insert_one({
            "email": email,
            "name": request.form['name'],
            "password": request.form['password'], # In a real app, hash this password!
            "logins": 0
        })
        return redirect('/login')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = users_collection.find_one({"email": email})
        if user and user['password'] == password: # Again, compare with hashed password in real app
            session['user'] = email
            users_collection.update_one({"email": email}, {"$inc": {"logins": 1}})
            return redirect('/dashboard') # Correct redirect to the dashboard route
        return render_template('login.html', message="Invalid credentials.")
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')
    email = session['user']
    user = users_collection.find_one({"email": email})
    if not user: # Handle case where user might be missing from DB
        session.clear()
        return redirect('/login')
    bookings = list(bookings_collection.find({'user_email': email}).sort('booking_date', -1)) # Sort by date
    return render_template('dashboard.html', name=user['name'], bookings=bookings)

@app.route('/bus')
def bus_booking_page():
    return render_template('bus.html')

@app.route('/train')
def train_booking_page():
    return render_template('train.html') # Assuming your train page is 'train.html'

@app.route('/flight')
def flight_booking_page():
    return render_template('flight.html')

@app.route('/hotel')
def hotel_booking_page():
    return render_template('hotel.html')

# This route now renders the seat selection page and passes all required info
@app.route('/select_seats')
def select_seats():
    if 'user' not in session:
        return redirect('/login')

    # Extract all necessary parameters from the URL
    booking_type = request.args.get('bookingType') # 'bus' or 'train'
    name = request.args.get('name') # Bus/Train name
    source = request.args.get('source')
    destination = request.args.get('destination')
    time = request.args.get('time') # Departure/Travel time
    vehicle_type = request.args.get('vehicleType') # AC Sleeper, Express etc.
    price_per_person = float(request.args.get('price')) # Convert to float
    travel_date = request.args.get('date')
    num_persons = int(request.args.get('persons'))

    # Construct a unique ID for this specific journey to fetch its booked seats
    # In a real system, this would be a proper ID from your bus/train data model
    journey_id = f"{source}{destination}{name}_{time}"
    
    # Fetch already booked seats for this specific journey (using dummy data for now)
    # In a real app, you'd query your database for bookings related to this journey on this date
    # Example: booked_seats_for_journey = bookings_collection.find({"journey_id": journey_id, "date": travel_date})
    # Then extract their 'seats' fields.
    existing_booked_seats = dummy_bus_train_data.get(journey_id, {}).get("booked_seats", [])

    return render_template('select_seats.html',
                           booking_type=booking_type,
                           name=name,
                           source=source,
                           destination=destination,
                           time=time,
                           vehicle_type=vehicle_type,
                           price_per_person=price_per_person,
                           travel_date=travel_date,
                           num_persons=num_persons,
                           booked_seats_json=jsonify(existing_booked_seats).get_data(as_text=True) # Pass as JSON string
                          )

# New POST route to handle seat booking submission
@app.route('/book_selected_seats', methods=['POST'])
def book_selected_seats():
    if 'user' not in session:
        return jsonify({"success": False, "message": "User not logged in"}), 401

    try:
        data = request.get_json() # Get JSON data from frontend

        booking_type = data.get('bookingType')
        name = data.get('name')
        source = data.get('source')
        destination = data.get('destination')
        time = data.get('time')
        vehicle_type = data.get('vehicleType')
        price_per_person = data.get('pricePerPerson')
        travel_date = data.get('travelDate')
        num_persons = data.get('numPersons')
        selected_seats = data.get('selectedSeats')
        total_price = data.get('totalPrice')

        if not selected_seats:
            return jsonify({"success": False, "message": "No seats selected."}), 400
        
        # Basic validation for number of persons vs selected seats
        if len(selected_seats) != num_persons:
             return jsonify({"success": False, "message": f"Please select exactly {num_persons} seats."}), 400


        user_email = session['user']
        
        # --- Critical Section for Real-time Booking ---
        # In a real application, THIS is where you'd implement concurrency control:
        # 1. Fetch current seat status from DB for this journey and date.
        # 2. Check if any selected_seats are already booked by another user since the page loaded.
        # 3. If conflicts, return an error.
        # 4. If no conflicts, atomically (e.g., using transactions or specific update operations)
        #    update the journey's booked seats in your database.
        # 5. Only then, proceed with creating the booking record for the user.
        #
        # For this demo, we'll just save it directly to the user's bookings.
        # This will NOT prevent double-booking if multiple users select the same seats simultaneously.
        # You'd need a dedicated collection for journeys (buses/trains running on specific dates)
        # to manage seat availability.
        # --- End Critical Section ---

        booking_record = {
            "user_email": user_email,
            "booking_type": booking_type,
            "name": name,
            "source": source,
            "destination": destination,
            "travel_time": time,
            "vehicle_type": vehicle_type,
            "travel_date": travel_date,
            "num_persons": num_persons,
            "selected_seats": selected_seats,
            "price_per_person": price_per_person,
            "total_price": total_price,
            "booking_date": datetime.now()
        }

        bookings_collection.insert_one(booking_record)

        return jsonify({"success": True, "message": "Seats booked successfully!", "redirect": "/dashboard"})

    except Exception as e:
        print(f"Error booking seats: {e}")
        return jsonify({"success": False, "message": "An error occurred during booking."}), 500


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)



from flask import Flask, render_template, request, redirect, session, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId # Import ObjectId for potential booking IDs
import os
from datetime import datetime

# Flask App Setup
app = Flask(__name__)
app = Flask()
app.secret_key = 'e0d15ae2faa18025f4e2a0c7dc5a7b8a830791cc83ad7538667ce14ca2ad8bc0'

# MongoDB Atlas Setup
client = MongoClient("mongodb+srv://srikalyani:Yank&2000@cluster0.vnew545.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client['Travelgo']
users_collection = db['users']
bookings_collection = db['bookings']

# --- Dummy Data (In a real app, these would come from your database) ---
# This is just for demonstration, as we're not persisting bus/train availability yet.
# For actual seat selection, you'd query specific journey's seat data.
dummy_bus_train_data = {
    "Hyderabad_Vijayawada_Orange Travels_08:00 AM": { # Example unique ID for a journey
        "total_seats": 30,
        "booked_seats": ["A1", "A2", "B3"] # Example: These seats are already booked
    },
    "Hyderabad_Vijayawada_Andhra Pradesh Express_06:00": {
        "total_seats": 50,
        "booked_seats": ["C5", "C6", "D1"]
    }
    # Add more entries for other unique bus/train journeys
}
# --- End Dummy Data ---


@app.route('/')
def home():
    return render_template('index.html', logged_in='user' in session)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        if users_collection.find_one({"email": email}):
            return render_template('register.html', message="User already exists.")
        users_collection.insert_one({
            "email": email,
            "name": request.form['name'],
            "password": request.form['password'], # In a real app, hash this password!
            "logins": 0
        })
        return redirect('/login')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = users_collection.find_one({"email": email})
        if user and user['password'] == password: # Again, compare with hashed password in real app
            session['user'] = email
            users_collection.update_one({"email": email}, {"$inc": {"logins": 1}})
            return redirect('/dashboard') # Correct redirect to the dashboard route
        return render_template('login.html', message="Invalid credentials.")
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')
    email = session['user']
    user = users_collection.find_one({"email": email})
    if not user: # Handle case where user might be missing from DB
        session.clear()
        return redirect('/login')
    bookings = list(bookings_collection.find({'user_email': email}).sort('booking_date', -1)) # Sort by date
    return render_template('dashboard.html', name=user['name'], bookings=bookings)

@app.route('/bus')
def bus_booking_page():
    return render_template('bus.html')

@app.route('/train')
def train_booking_page():
    return render_template('train.html') # Assuming your train page is 'train.html'

@app.route('/flight')
def flight_booking_page():
    return render_template('flight.html')

@app.route('/hotel')
def hotel_booking_page():
    return render_template('hotel.html')

# This route now renders the seat selection page and passes all required info
@app.route('/select_seats')
def select_seats():
    if 'user' not in session:
        return redirect('/login')

    # Extract all necessary parameters from the URL
    booking_type = request.args.get('bookingType') # 'bus' or 'train'
    name = request.args.get('name') # Bus/Train name
    source = request.args.get('source')
    destination = request.args.get('destination')
    time = request.args.get('time') # Departure/Travel time
    vehicle_type = request.args.get('vehicleType') # AC Sleeper, Express etc.
    price_per_person = float(request.args.get('price')) # Convert to float
    travel_date = request.args.get('date')
    num_persons = int(request.args.get('persons'))

    # Construct a unique ID for this specific journey to fetch its booked seats
    # In a real system, this would be a proper ID from your bus/train data model
    journey_id = f"{source}{destination}{name}_{time}"
    
    # Fetch already booked seats for this specific journey (using dummy data for now)
    # In a real app, you'd query your database for bookings related to this journey on this date
    # Example: booked_seats_for_journey = bookings_collection.find({"journey_id": journey_id, "date": travel_date})
    # Then extract their 'seats' fields.
    existing_booked_seats = dummy_bus_train_data.get(journey_id, {}).get("booked_seats", [])

    import json
    return render_template('select_seats.html',
                           booking_type=booking_type,
                           name=name,
                           source=source,
                           destination=destination,
                           time=time,
                           vehicle_type=vehicle_type,
                           price_per_person=price_per_person,
                           travel_date=travel_date,
                           num_persons=num_persons,
                           booked_seats_json=json.dumps(existing_booked_seats) # Pass as JSON string
                          )

# New POST route to handle seat booking submission
@app.route('/book_selected_seats', methods=['POST'])
def book_selected_seats():
    if 'user' not in session:
        return jsonify({"success": False, "message": "User not logged in"}), 401

    try:
        data = request.get_json() # Get JSON data from frontend

        booking_type = data.get('bookingType')
        name = data.get('name')
        source = data.get('source')
        destination = data.get('destination')
        time = data.get('time')
        vehicle_type = data.get('vehicleType')
        price_per_person = data.get('pricePerPerson')
        travel_date = data.get('travelDate')
        num_persons = data.get('numPersons')
        selected_seats = data.get('selectedSeats')
        total_price = data.get('totalPrice')

        if not selected_seats:
            return jsonify({"success": False, "message": "No seats selected."}), 400
        
        # Basic validation for number of persons vs selected seats
        if len(selected_seats) != num_persons:
             return jsonify({"success": False, "message": f"Please select exactly {num_persons} seats."}), 400


        user_email = session['user']
        
        # --- Critical Section for Real-time Booking ---
        # In a real application, THIS is where you'd implement concurrency control:
        # 1. Fetch current seat status from DB for this journey and date.
        # 2. Check if any selected_seats are already booked by another user since the page loaded.
        # 3. If conflicts, return an error.
        # 4. If no conflicts, atomically (e.g., using transactions or specific update operations)
        #    update the journey's booked seats in your database.
        # 5. Only then, proceed with creating the booking record for the user.
        #
        # For this demo, we'll just save it directly to the user's bookings.
        # This will NOT prevent double-booking if multiple users select the same seats simultaneously.
        # You'd need a dedicated collection for journeys (buses/trains running on specific dates)
        # to manage seat availability.
        # --- End Critical Section ---

        booking_record = {
            "user_email": user_email,
            "booking_type": booking_type,
            "name": name,
            "source": source,
            "destination": destination,
            "travel_time": time,
            "vehicle_type": vehicle_type,
            "travel_date": travel_date,
            "num_persons": num_persons,
            "selected_seats": selected_seats,
            "price_per_person": price_per_person,
            "total_price": total_price,
            "booking_date": datetime.now()
        }

        bookings_collection.insert_one(booking_record)

        return jsonify({"success": True, "message": "Seats booked successfully!", "redirect": "/dashboard"})

    except Exception as e:
        print(f"Error booking seats: {e}")
        return jsonify({"success": False, "message": "An error occurred during booking."}), 500


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)