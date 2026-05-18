def patch_aws_py_literal():
    path = 'app/scanners/aws.py'
    with open(path, 'r', encoding='utf-8') as f:
        code = f.read()

    # 1. dataclass
    if "access_denied_services: List[str] = None" not in code:
        code = code.replace(
            "regions_scanned: int",
            "regions_scanned: int\n    access_denied_services: List[str] = None"
        )
    
    # 2. init
    if "self.access_denied_services = set()" not in code:
        code = code.replace(
            "self.executor = ThreadPoolExecutor(max_workers=10)",
            "self.executor = ThreadPoolExecutor(max_workers=10)\n        self.access_denied_services = set()"
        )

    # 3. method
    handle_error = """
    def _handle_scan_error(self, service: str, error: Exception, region: str = None):
        err_str = str(error)
        if 'AccessDenied' in err_str or 'UnauthorizedOperation' in err_str:
            self.access_denied_services.add(service)
        if region:
            print(f"⚠️ {service} scan error in {region}: {error}")
        else:
            print(f"⚠️ {service} scan error: {error}")
"""
    if "_handle_scan_error" not in code:
        code = code.replace("self.access_denied_services = set()", "self.access_denied_services = set()\n" + handle_error)

    # 4. result
    if "access_denied_services=list(self.access_denied_services)" not in code:
        code = code.replace(
            "regions_scanned=len(self.regions)\n        )",
            "regions_scanned=len(self.regions),\n            access_denied_services=list(self.access_denied_services)\n        )"
        )

    # 5. Literal replacements
    replacements = [
        ('            except Exception as e:\n                logger.warning(f"EC2 scan error in {region}: {e}")',
         '            except Exception as e:\n                self._handle_scan_error("EC2", e, region)'),
        ('            except Exception as e:\n                logger.warning(f"EBS scan error in {region}: {e}")',
         '            except Exception as e:\n                self._handle_scan_error("EBS", e, region)'),
        ('            except Exception as e:\n                logger.warning(f"Elastic IP scan error in {region}: {e}")',
         '            except Exception as e:\n                self._handle_scan_error("Elastic IP", e, region)'),
        ('            except Exception as e:\n                logger.warning(f"VPC scan error in {region}: {e}")',
         '            except Exception as e:\n                self._handle_scan_error("VPC", e, region)'),
        ('            except Exception as e:\n                logger.warning(f"Subnet scan error in {region}: {e}")',
         '            except Exception as e:\n                self._handle_scan_error("Subnet", e, region)'),
        ('            except Exception as e:\n                logger.warning(f"Security Group scan error in {region}: {e}")',
         '            except Exception as e:\n                self._handle_scan_error("Security Group", e, region)'),
        ('            except Exception as e:\n                logger.warning(f"Route Table scan error in {region}: {e}")',
         '            except Exception as e:\n                self._handle_scan_error("Route Table", e, region)'),
        ('            except Exception as e:\n                logger.warning(f"Internet Gateway scan error in {region}: {e}")',
         '            except Exception as e:\n                self._handle_scan_error("Internet Gateway", e, region)'),
        ('            except Exception as e:\n                logger.warning(f"Network ACL scan error in {region}: {e}")',
         '            except Exception as e:\n                self._handle_scan_error("Network ACL", e, region)'),
        ('            except Exception as e:\n                logger.warning(f"DHCP Options scan error in {region}: {e}")',
         '            except Exception as e:\n                self._handle_scan_error("DHCP Options", e, region)'),
        ('            except Exception as e:\n                logger.warning(f"Key Pair scan error in {region}: {e}")',
         '            except Exception as e:\n                self._handle_scan_error("Key Pair", e, region)'),
        ('            except Exception as e:\n                logger.warning(f"IAM Users scan error: {e}")',
         '            except Exception as e:\n                self._handle_scan_error("IAM Users", e)'),
        ('            except Exception as e:\n                logger.warning(f"IAM Roles scan error: {e}")',
         '            except Exception as e:\n                self._handle_scan_error("IAM Roles", e)'),
        ('            except Exception as e:\n                logger.warning(f"RDS scan failed in {region}: {e}")',
         '            except Exception as e:\n                self._handle_scan_error("RDS", e, region)'),
        ('            except Exception as e:\n                logger.warning(f"Lambda scan failed in {region}: {e}")',
         '            except Exception as e:\n                self._handle_scan_error("Lambda", e, region)'),
        ('            except Exception as e:\n                logger.warning(f"S3 scan failed: {e}")',
         '            except Exception as e:\n                self._handle_scan_error("S3", e)')
    ]

    for old, new in replacements:
        if old in code:
            code = code.replace(old, new)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(code)

if __name__ == "__main__":
    patch_aws_py_literal()
    print("Done")
