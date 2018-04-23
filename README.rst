===================================================
Python API for Deltran Battery Tender WiFi products
===================================================


Installation
============

.. code-block:: bash

    pip install batterytender


Usage
=====

Module
------

You can import the module as ``batterytender``.

.. code-block:: python

    import batterytender

    email = 'XXXXXXXXXXXXXXXXXXXX'
    password = 'XXXXXXXXXXXXXXXXXXXX'

    bt = batterytender.BatteryTender(email, password)

    for monitor in bt.monitors:
        print('Monitor id: {}'.format(monitor.device_id))
        print('    Name: {}'.format(monitor.name))
        print('    Date: {}'.format(monitor.date))
        print('    Voltage: {}'.format(monitor.voltage))


        # Historical readings
        print('    History:')
        for history in monitor.history:
            print('        Date: {}'.format(history['date']))
            print('        Voltage: {}'.format(history['voltage']))


        # The latest reading is also available in the same format as
        # historical reading via the `.current` property
        print('    Current:')
        print('        Date: {}'.format(monitor.current['date']))
        print('        Voltage: {}'.format(monitor.current['voltage']))
