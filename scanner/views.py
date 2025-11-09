from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import ScanRequest, ScanResult
from .forms import ScanRequestForm
from .services import logger


@login_required
def create_scan_request(request):
    if request.method == "POST":
        form = ScanRequestForm(request.POST)
        if form.is_valid():
            scan_request = form.save(commit=False)
            scan_request.user = request.user
            scan_request.status = "PENDING"
            scan_request.save()

            logger.info(f"Создан ScanRequest ID: {scan_request.id}")

            # синхронный вызов для отладки
            from .services import ScanProcessor

            ScanProcessor.process_scan(scan_request.id)

            # позже: ScanProcessor.start_scan_async(scan_request.id)

            messages.success(
                request, "Запрос на сканирование успешно создан! Сканирование запущено."
            )
            return redirect("scan_requests_list")
    else:
        form = ScanRequestForm()

    return render(request, "scanner/create_scan_request.html", {"form": form})


@login_required
def scan_requests_list(request):
    scan_requests = ScanRequest.objects.filter(user=request.user).order_by(
        "-created_at"
    )
    return render(
        request, "scanner/scan_requests_list.html", {"scan_requests": scan_requests}
    )


@login_required
def scan_request_detail(request, pk):
    scan_request = get_object_or_404(ScanRequest, pk=pk, user=request.user)
    scan_results = scan_request.scan_results.all()
    return render(
        request,
        "scanner/scan_request_detail.html",
        {"scan_request": scan_request, "scan_results": scan_results},
    )
