# Disable the broken deepeval pytest plugin (incompatible with current openai package).
collect_ignore_glob = []

def pytest_configure(config):
    # Prevent deepeval's broken plugin from poisoning the pytest session.
    try:
        config.pluginmanager.set_blocked("deepeval")
    except Exception:
        pass
