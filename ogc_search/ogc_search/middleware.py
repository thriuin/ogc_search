import json
import logging
import datetime


class QueryLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.
        self.logger = logging.getLogger('ogc_search')

    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.

        response = self.get_response(request)

        if request.path in ['/en/od/', '/fr/od/', '/en/export/', '/fr/export']:
            # Code to be executed for each request/response after
            # the view is called.
            log_dict = request.GET.copy()
            log_dict['path'] = request.path

            log_dict['timestamp'] = datetime.datetime.now().replace(microsecond=0).isoformat()
            self.logger.info(json.dumps(log_dict))
        return response
