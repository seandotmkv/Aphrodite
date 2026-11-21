"""Publish the current installation stage from the ordered backend job queue."""

import libcalamares


def pretty_name():
    return libcalamares.job.configuration["label"]


def run():
    libcalamares.globalstorage.insert("seanInstallPhase", libcalamares.job.configuration["phase"])
    return None
